from __future__ import annotations
import asyncio, json, os, statistics, time
from pathlib import Path
import aiohttp
from src.evaluation.compliance_scorer import (
    BEHAVIORAL_JUDGE_SYSTEM,
    BEHAVIORAL_JUDGE_USER,
    LANGUAGE_JUDGE_SYSTEM,
    LANGUAGE_JUDGE_USER,
)
from src.evaluation.judge_config import resolve_judge_config, build_judge_headers, build_judge_payload

ROOT = Path('/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops')
RESULT = ROOT / 'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl'
OUT = ROOT / '.tmp/q1_judge_concurrency_probe.json'
LEVELS = [1, 2, 4, 6, 8, 12]
N_PER_LEVEL = 24

os.environ['JUDGE_PROVIDER'] = 'vllm'
os.environ['JUDGE_API_URL'] = 'http://210.179.28.26:18000/v1/chat/completions'
os.environ['JUDGE_MODEL_NAME'] = 'cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit'
os.environ.setdefault('JUDGE_MAX_TOKENS', '256')

config = resolve_judge_config()
headers = build_judge_headers(config)

def collect_payloads(limit: int):
    payloads = []
    records_seen = 0
    with RESULT.open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            records_seen += 1
            rules = r.get('rules', [])
            for t in r.get('turn_results', []):
                scores = t.get('scores', [])
                for i, s in enumerate(scores):
                    method = s.get('method')
                    if s.get('pass') is not None or method not in {'llm_judge','llm_language_judge'}:
                        continue
                    rule = rules[i] if i < len(rules) else {'rule_id': s.get('rule_id'), 'text': ''}
                    if method == 'llm_language_judge':
                        user_content = LANGUAGE_JUDGE_USER.format(
                            rule_text=rule.get('text',''),
                            user_message=t.get('user_message',''),
                            response=t.get('response',''),
                        )
                        messages = [{'role':'system','content':LANGUAGE_JUDGE_SYSTEM}, {'role':'user','content':user_content}]
                    else:
                        user_content = BEHAVIORAL_JUDGE_USER.format(
                            rule_text=rule.get('text',''),
                            user_message=t.get('user_message',''),
                            response=t.get('response',''),
                        )
                        messages = [{'role':'system','content':BEHAVIORAL_JUDGE_SYSTEM}, {'role':'user','content':user_content}]
                    payload = build_judge_payload(messages, config)
                    payloads.append({'payload': payload, 'method': method, 'rule_id': rule.get('rule_id'), 'case_id': r.get('case_id'), 'turn': t.get('turn')})
                    if len(payloads) >= limit:
                        return payloads, records_seen
    return payloads, records_seen

async def run_level(level: int, tasks):
    sem = asyncio.Semaphore(level)
    latencies = []
    statuses = []
    usages = []
    errors = []
    started = time.perf_counter()
    timeout = aiohttp.ClientTimeout(total=120, connect=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async def one(item, idx):
            async with sem:
                st = time.perf_counter()
                try:
                    async with session.post(config['api_url'], headers=headers, json=item['payload']) as resp:
                        text = await resp.text()
                        latency = time.perf_counter() - st
                        statuses.append(resp.status)
                        latencies.append(latency)
                        try:
                            data = json.loads(text)
                            if 'usage' in data:
                                usages.append(data['usage'])
                            if resp.status != 200:
                                errors.append({'idx': idx, 'status': resp.status, 'text': text[:300]})
                        except Exception as e:
                            errors.append({'idx': idx, 'status': resp.status, 'parse_error': str(e), 'text': text[:300]})
                except Exception as e:
                    latencies.append(time.perf_counter() - st)
                    statuses.append('EXC')
                    errors.append({'idx': idx, 'exception': repr(e)})
        await asyncio.gather(*(one(item, idx) for idx, item in enumerate(tasks)))
    wall = time.perf_counter() - started
    ok = sum(1 for s in statuses if s == 200)
    prompt_tokens = sum(u.get('prompt_tokens',0) for u in usages)
    completion_tokens = sum(u.get('completion_tokens',0) for u in usages)
    total_tokens = sum(u.get('total_tokens',0) for u in usages)
    return {
        'concurrency': level,
        'requests': len(tasks),
        'ok': ok,
        'errors': errors[:5],
        'wall_seconds': wall,
        'requests_per_second': ok / wall if wall else 0,
        'latency_p50': statistics.median(latencies) if latencies else None,
        'latency_p95': statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else (max(latencies) if latencies else None),
        'latency_max': max(latencies) if latencies else None,
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'total_tokens': total_tokens,
        'tokens_per_second': total_tokens / wall if wall and total_tokens else None,
        'sample_methods': {m: sum(1 for it in tasks if it['method']==m) for m in sorted({it['method'] for it in tasks})},
    }

async def main():
    needed = len(LEVELS) * N_PER_LEVEL
    payloads, records_seen = collect_payloads(needed)
    if len(payloads) < needed:
        raise SystemExit(f'not enough payloads: {len(payloads)} < {needed}')
    results = []
    for pos, level in enumerate(LEVELS):
        tasks = payloads[pos*N_PER_LEVEL:(pos+1)*N_PER_LEVEL]
        print(f'RUN level={level} requests={len(tasks)} first={tasks[0]["case_id"]}/{tasks[0]["rule_id"]}')
        res = await run_level(level, tasks)
        print(json.dumps(res, ensure_ascii=False))
        results.append(res)
        await asyncio.sleep(2)
    summary = {'config': config, 'levels': LEVELS, 'n_per_level': N_PER_LEVEL, 'records_seen_for_payload_collection': records_seen, 'result_path': str(RESULT), 'results': results, 'created_at': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'WROTE {OUT}')

if __name__ == '__main__':
    asyncio.run(main())

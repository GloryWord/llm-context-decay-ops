"""Fast experiment runner: auto-scoring only, deferred LLM-judge, case-level concurrency.

Phase 1: Run inference + auto-scoring (no judge calls) — ~10x faster
Phase 2: Batch LLM-judge for behavioral rules (separate pass)

Usage:
    # Fast inference (no judge)
    python3 scripts/run_experiment_fast.py --models vllm --reps 5 --concurrency 3

    # After inference, run batch judge
    python3 scripts/run_experiment_fast.py --judge-only --input data/outputs/main_experiment/fast_results_*.jsonl
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.evaluation.compliance_scorer import (
    compute_compliance_rate,
    score_behavioral_async,
    score_rules,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================
# Model configurations
# ============================================================

MODEL_CONFIGS: dict[str, dict] = {
    "vllm": {
        "api_url": os.getenv("VLLM_API_URL", "http://210.179.28.26:18000/v1/chat/completions"),
        "model_name": os.getenv("EVAL_MODEL_NAME", "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4"),
        "api_key": os.getenv("OPENROUTER_API_KEY", "dummy_token_for_local_vllm"),
        "extra_params": {},
    },
    "deepseek-r1": {
        "api_url": "https://openrouter.ai/api/v1/chat/completions",
        "model_name": "deepseek/deepseek-r1",
        "api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "extra_params": {},
    },
}

JUDGE_HEADERS = {
    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}",
    "HTTP-Referer": "http://localhost",
    "Content-Type": "application/json",
}

CASES_FILE = ROOT / "data" / "processed" / "experiment_cases_full.jsonl"
OUTPUT_DIR = ROOT / "data" / "outputs" / "main_experiment"


async def call_model(
    session: aiohttp.ClientSession,
    model_cfg: dict,
    messages: list[dict],
) -> str:
    """Call target model API with retry."""
    headers = {
        "Authorization": f"Bearer {model_cfg['api_key']}",
        "HTTP-Referer": "http://localhost",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_cfg["model_name"],
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 512,
        **model_cfg.get("extra_params", {}),
    }

    for attempt in range(3):
        try:
            async with session.post(model_cfg["api_url"], headers=headers, json=payload) as resp:
                if resp.status == 429:
                    await asyncio.sleep(2 ** attempt * 5)
                    continue
                result = await resp.json()
                if "choices" in result and result["choices"]:
                    return result["choices"][0]["message"]["content"]
                logger.warning("API error: %s", result.get("error", {}).get("message", str(result))[:100])
                await asyncio.sleep(2 ** attempt)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning("Request failed (attempt %d): %s", attempt + 1, e)
            await asyncio.sleep(2 ** attempt)
    return "[ERROR] All retries failed"


async def run_single_case_fast(
    session: aiohttp.ClientSession,
    model_cfg: dict,
    case: dict,
    rep: int,
) -> dict:
    """Run case with auto-scoring only (no judge). ~10x faster."""
    messages: list[dict] = [{"role": "system", "content": case["system_prompt"]}]
    turn_results: list[dict] = []

    for turn_info in case["conversation_template"]:
        user_content = turn_info["content"]
        messages.append({"role": "user", "content": user_content})

        response = await call_model(session, model_cfg, messages)
        messages.append({"role": "assistant", "content": response})

        # Auto-scoring only — behavioral rules stay as pending (None)
        scores = score_rules(response, case["rules"])
        compliance = compute_compliance_rate(scores)

        turn_results.append({
            "turn": turn_info["turn"],
            "user_message": user_content,
            "response": response,
            "scores": scores,
            "compliance_rate": compliance,
            "response_length": len(response),
        })

    return {
        "case_id": case["case_id"],
        "rep": rep,
        "model": model_cfg["model_name"],
        "research_question": case.get("research_question", ""),
        "rule_count": case["rule_count"],
        "turn_count": case["turn_count"],
        "attack_intensity": case["attack_intensity"],
        "rule_set_variant": case.get("rule_set_variant", []),
        "rules": case["rules"],
        "turn_results": turn_results,
        "judge_status": "pending",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def load_checkpoint(output_path: Path) -> set[str]:
    """Load completed run IDs from checkpoint file."""
    completed: set[str] = set()
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    run_id = f"{rec['case_id']}_{rec['rep']}_{rec['model']}"
                    completed.add(run_id)
    return completed


async def run_experiment_fast(
    models: list[str],
    reps: int = 5,
    concurrency: int = 3,
    dry_run: bool = False,
) -> None:
    """Run experiment with case-level concurrency, no judge calls."""
    cases: list[dict] = []
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))

    if dry_run:
        cases = cases[:10]
        reps = 1

    total = len(cases) * reps * len(models)
    logger.info("Fast experiment: %d cases × %d reps × %d models = %d runs (concurrency=%d)",
                len(cases), reps, len(models), total, concurrency)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for model_key in models:
        model_cfg = MODEL_CONFIGS[model_key]
        model_slug = model_cfg["model_name"].replace("/", "_")
        output_path = OUTPUT_DIR / f"fast_results_{model_slug}.jsonl"

        completed = load_checkpoint(output_path)
        logger.info("Model %s: %d already completed", model_key, len(completed))

        # Build work queue
        work: list[tuple[dict, int]] = []
        for rep in range(reps):
            for case in cases:
                run_id = f"{case['case_id']}_{rep}_{model_cfg['model_name']}"
                if run_id not in completed:
                    work.append((case, rep))

        logger.info("Remaining: %d runs", len(work))
        if not work:
            continue

        semaphore = asyncio.Semaphore(concurrency)
        timeout = aiohttp.ClientTimeout(total=120, connect=15)
        done_count = 0
        out_lock = asyncio.Lock()

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async def bounded_run(case_arg: dict, rep_arg: int) -> None:
                nonlocal done_count
                async with semaphore:
                    result = await run_single_case_fast(session, model_cfg, case_arg, rep_arg)

                async with out_lock:
                    with open(output_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(result, ensure_ascii=False) + "\n")
                    done_count += 1
                    if done_count % 20 == 0 or done_count == len(work):
                        final_c = result["turn_results"][-1]["compliance_rate"] if result["turn_results"] else 0
                        logger.info("[%d/%d] %s rep=%d → %.0f%%",
                                    done_count, len(work), case_arg["case_id"], rep_arg, final_c * 100)

            tasks = [bounded_run(c, r) for c, r in work]
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Model %s done: %d runs", model_key, done_count)


# ============================================================
# Phase 2: Batch judge
# ============================================================

async def batch_judge(input_patterns: list[str], concurrency: int = 10) -> None:
    """Post-process: score all pending behavioral rules via LLM-judge."""
    import glob

    records: list[dict] = []
    file_map: dict[str, list[dict]] = {}

    for pattern in input_patterns:
        for path in sorted(glob.glob(pattern)):
            file_records = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        file_records.append(json.loads(line))
            file_map[path] = file_records
            records.extend(file_records)

    # Count pending judge calls
    pending_count = 0
    for r in records:
        for t in r.get("turn_results", []):
            for s in t.get("scores", []):
                if s.get("method") == "llm_judge" and s.get("pass") is None:
                    if "pending" in s.get("detail", ""):
                        pending_count += 1

    logger.info("Total records: %d, pending judge calls: %d", len(records), pending_count)
    if pending_count == 0:
        logger.info("No pending judge calls")
        return

    semaphore = asyncio.Semaphore(concurrency)
    timeout = aiohttp.ClientTimeout(total=60, connect=15)
    judged_count = 0

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async def judge_one(r: dict, t: dict, i: int, rule: dict) -> None:
            nonlocal judged_count
            async with semaphore:
                result = await score_behavioral_async(
                    session, JUDGE_HEADERS, t["response"], rule, t["user_message"]
                )
                t["scores"][i] = result
                judged_count += 1
                if judged_count % 50 == 0:
                    logger.info("Judged %d/%d", judged_count, pending_count)

        tasks = []
        for r in records:
            rules = r.get("rules", [])
            for t in r.get("turn_results", []):
                for i, s in enumerate(t.get("scores", [])):
                    if (s.get("method") == "llm_judge"
                            and s.get("pass") is None
                            and "pending" in s.get("detail", "")):
                        rule = rules[i] if i < len(rules) else {"rule_id": s["rule_id"], "text": ""}
                        tasks.append(judge_one(r, t, i, rule))

        await asyncio.gather(*tasks, return_exceptions=True)

    # Recompute compliance and write back
    for r in records:
        for t in r.get("turn_results", []):
            t["compliance_rate"] = compute_compliance_rate(t["scores"])
        r["judge_status"] = "complete"

    for path, file_records in file_map.items():
        with open(path, "w", encoding="utf-8") as f:
            for r in file_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    logger.info("Batch judge complete: %d calls", judged_count)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fast experiment runner.")
    parser.add_argument("--models", nargs="+", default=["vllm"], choices=list(MODEL_CONFIGS.keys()))
    parser.add_argument("--reps", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--judge-only", action="store_true", help="Run batch judge on existing results.")
    parser.add_argument("--input", nargs="+", default=None, help="Input patterns for --judge-only.")
    args = parser.parse_args()

    if args.judge_only:
        patterns = args.input or [str(OUTPUT_DIR / "fast_results_*.jsonl")]
        asyncio.run(batch_judge(patterns, args.concurrency))
    else:
        asyncio.run(run_experiment_fast(args.models, args.reps, args.concurrency, args.dry_run))


if __name__ == "__main__":
    main()

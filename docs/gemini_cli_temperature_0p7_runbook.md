# Temperature 0.7 Full Run with Gemini CLI Judge

이 문서는 Google 계정 기반 Gemini CLI quota를 사용해 OpenRouter 비용 없이
`target model temperature=0.7` full run을 실행하는 절차를 정리한다.

## 핵심 원칙

- Target model temperature만 0.7로 변경한다.
- Judge temperature는 0.0으로 유지한다.
- Gemini CLI judge는 per-rule이 아니라 record 단위 batch로 실행한다.
- 기본 judge model alias는 `classifier`를 사용한다. 현재 Gemini CLI 기본 설정에서
  `classifier`는 zero-temperature `base` alias를 상속하는 분류용 alias다.
- Judge subprocess는 임시 cwd에서 실행해 repository `GEMINI.md`가 judge 판단에
  섞이지 않게 한다.

## Quota 계산

현재 full run 크기 기준:

- 전체 결과 record: 1,540개
- LLM judge가 필요한 score slot: 17,820개
- record 단위 Gemini CLI judge request: 약 1,400회

Google AI Pro/Google One AI Pro가 Gemini CLI에서 Pro quota로 인식되면 하루
1,500 requests 수준이므로, record-batch judge는 하루 안에 들어올 가능성이 있다.
단, 계정/인증 방식이 단순 Google account tier로 인식되면 1,000 requests/day일 수
있으므로 2일로 나눠 실행한다.

## 0. Gemini CLI 확인

```bash
gemini --version
gemini --help | head -40
```

가능하면 interactive Gemini에서 `/stats model`로 현재 quota/tier를 확인한다.

## 1. target temperature 0.7 full generation

```bash
cd /Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops

OUT07=data/outputs/temp0p7_llama_gemini_cli_judge
mkdir -p "$OUT07"

.venv/bin/python scripts/run_experiment_fast.py \
  --models vllm \
  --reps 5 \
  --concurrency 6 \
  --temperature 0.7 \
  --cases-file data/processed/experiment_cases_full.jsonl \
  --output-dir "$OUT07"
```

이 단계는 Llama/vLLM target 응답 생성만 수행한다. R01/behavioral judge는 pending으로 남는다.

## 2. Gemini CLI judge dry run

```bash
.venv/bin/python scripts/judge_with_gemini_cli.py \
  --input "$OUT07/fast_results_*.jsonl" \
  --model classifier \
  --concurrency 1 \
  --dry-run
```

예상: record 단위 judge jobs와 score slot 수가 출력된다.

## 3. 작은 pilot judge

```bash
.venv/bin/python scripts/judge_with_gemini_cli.py \
  --input "$OUT07/fast_results_*.jsonl" \
  --model classifier \
  --concurrency 1 \
  --limit 20
```

이후 pending 개수와 JSONL 상태를 확인한다.

```bash
.venv/bin/python - <<'PY'
import json, glob
from scripts.run_experiment_fast import count_unresolved_judge_scores
records=[]
for path in glob.glob('data/outputs/temp0p7_llama_gemini_cli_judge/fast_results_*.jsonl'):
    for line in open(path):
        if line.strip():
            records.append(json.loads(line))
print('records', len(records))
print('unresolved_judge_scores', count_unresolved_judge_scores(records))
print('judge_status_counts', {s: sum(1 for r in records if r.get('judge_status') == s) for s in {'pending','incomplete','complete'}})
PY
```

## 4. Full Gemini CLI judge

Google Pro quota를 하루에 모두 쓸 계획이면:

```bash
.venv/bin/python scripts/judge_with_gemini_cli.py \
  --input "$OUT07/fast_results_*.jsonl" \
  --model classifier \
  --concurrency 1 \
  --timeout 180
```

1,000 requests/day tier로 잡히거나 quota가 걱정되면 첫날 900개만 실행한다.
이미 채점된 record는 다음 실행에서 자동으로 skip된다.

```bash
.venv/bin/python scripts/judge_with_gemini_cli.py \
  --input "$OUT07/fast_results_*.jsonl" \
  --model classifier \
  --concurrency 1 \
  --timeout 180 \
  --limit 900
```

다음날 같은 명령에서 `--limit`를 빼고 이어서 실행한다.

## 5. Reaggregate and report

```bash
.venv/bin/python scripts/reaggregate_metrics.py \
  --input "$OUT07/fast_results_*.jsonl" \
  --cases data/processed/experiment_cases_full.jsonl \
  --output-dir "$OUT07/reaggregated"
```

필요하면 temp0 결과와 temp0.7 결과 비교용 figure/report 생성 스크립트를 별도로 추가한다.
현재 `generate_metric_reanalysis_html.py`는 temp0 재분석 HTML 중심이다.

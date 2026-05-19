# Worker-2 orchestration/readiness recommendations

## Scope and guardrail

- Team task: inspect/adapt run orchestration and remote vLLM readiness for the Q1 target-balanced full rerun.
- Guardrail from leader mailbox: **do not start a duplicate full remote run**. I did not start target generation or judge runs; only local generation probes, static syntax checks, unit tests, and one low-token readiness probe against the currently exposed Gemma endpoint were run.

## Recommended script changes applied locally

1. `scripts/test_vllm_conn.py`
   - Replace the previous best-effort inference smoke test with a failing readiness probe.
   - Require a configured chat-completions URL and model (`--api-url`/`VLLM_API_URL`, `--model`/`EVAL_MODEL_NAME`).
   - Infer or accept `/v1/models` (`--models-url`/`VLLM_MODELS_URL`).
   - Verify the expected model is listed by `/v1/models` unless `--skip-models` is passed.
   - Verify `/v1/chat/completions` returns HTTP 200, object JSON, at least one choice, and non-empty assistant content.
   - Use `src.utils.http_headers.build_json_headers` so local vLLM does not receive an unrelated dummy bearer token.
   - Exit non-zero on readiness failure so orchestration can block before a long run.

2. `.tmp/run_q1_sampled_llama_then_gemma.sh`
   - Default to target-balanced paths:
     - `data/processed/q1_target_balanced_q2_injection_cases.jsonl`
     - `data/processed/q1_target_balanced_q2_injection_cases_trace.csv`
     - `data/outputs/2026-05-19_q1_target_balanced_local_llama_gemma/`
   - Generate cases with `scripts/generate_q1_sampled_cases.py --all-target-rules` before the run.
   - Remove hardcoded `341` validation and logging thresholds; compute expected records and turns from the generated cases file.
   - Add manifest fields for target-rule distribution and `r08_absent_verified`.
   - Strengthen `wait_for_model` so `/v1/models` membership is necessary but not sufficient: the helper must also pass a tiny chat-completion readiness probe.

## Validation thresholds for leader run

### Readiness thresholds

- Llama target container readiness:
  - Expected model: `hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4`.
  - `/v1/models` must list the expected model.
  - `scripts/test_vllm_conn.py --quiet --timeout 30 --max-tokens 8` must pass with non-empty completion text.
  - Polling budget in the script: 240 attempts × 5 seconds.

- Gemma judge container readiness:
  - Expected model: `cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit`.
  - `/v1/models` must list the expected model.
  - `scripts/test_vllm_conn.py --quiet --timeout 30 --max-tokens 8` must pass with non-empty completion text.
  - Polling budget in the script: 180 attempts × 5 seconds.

### Target-balanced case thresholds

Local all-target probe evidence (`generate_probe_summary.json`):

- Total cases: `3069`.
- Total target turn calls: `25668`.
- Target rules: `R01,R02,R03,R04,R05,R06,R07,R09,R10`.
- Per-target cases: `341` each.
- R08 presence: `false`.
- Rule-count distribution: `{1: 99, 3: 990, 5: 990, 7: 990}`.
- Turn-count distribution: `{1: 558, 5: 837, 10: 837, 15: 837}`.
- Condition distribution: `{benign_context: 1116, injection_context: 1953}`.

### Target generation validation thresholds

The target validation block should fail unless all are true:

- `len(records) == len(cases)`.
- Result `case_id` set exactly matches generated case `case_id` set.
- No duplicate result `case_id` values.
- For every record, `len(turn_results) == case.turn_count`.
- No turn response starts with `[ERROR]`.
- Generated cases contain no `R08` in `rule_set_variant` or `system_prompt`.

### Judge validation thresholds

The judge validation block should fail unless all are true:

- `len(records) == len(cases)`.
- `unresolved_judge_scores == 0`.
- `judge_status_counts.complete == len(cases)`.

## Evidence collected

- Read: `AGENTS.md` for evidence-first workflow and source reporting.
- Read: team inbox/task/config under `$OMX_TEAM_STATE_ROOT/team/q1-target-balanced-fu-eb99b960/`.
- Read/changed: `scripts/test_vllm_conn.py`.
- Read/changed: `.tmp/run_q1_sampled_llama_then_gemma.sh`.
- Read: `scripts/generate_q1_sampled_cases.py` for `--all-target-rules` behavior.
- Read: `tests/test_generate_q1_sampled_cases.py`, `tests/test_run_experiment_fast_config.py`, and `tests/test_http_headers.py` for existing expectations.
- Read: prior run manifest and validation summaries under `data/outputs/2026-05-18_q1_sampled_local_llama_gemma/` to confirm old R03-only run completed but was hardcoded to 341 records.
- Checked current remote `/v1/models`: currently exposes Gemma judge model.
- Ran one low-token current Gemma readiness probe; result passed.

## Commands and results

- `bash -n .tmp/run_q1_sampled_llama_then_gemma.sh` → PASS.
- `.venv/bin/python scripts/generate_q1_sampled_cases.py --all-target-rules --output .tmp/q1_target_balanced_team/worker-2/q1_target_balanced_cases_probe.jsonl --trace-csv .tmp/q1_target_balanced_team/worker-2/q1_target_balanced_cases_probe_trace.csv` → PASS; summary retained, large probe JSONL/CSV removed after counting.
- `VLLM_API_URL=http://210.179.28.26:18000/v1/chat/completions VLLM_MODELS_URL=http://210.179.28.26:18000/v1/models EVAL_MODEL_NAME=cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit .venv/bin/python scripts/test_vllm_conn.py --quiet --timeout 30 --max-tokens 4` → PASS.
- `.venv/bin/python -m py_compile scripts/test_vllm_conn.py tests/test_vllm_readiness.py` → PASS.
- `.venv/bin/python -m ruff check ...` → not run; `ruff` is not installed in the repo venv.
- `.venv/bin/python -m pytest tests/test_vllm_readiness.py tests/test_run_experiment_fast_config.py tests/test_http_headers.py -q` → PASS, 18 tests.
- `.venv/bin/python -m pytest -q` → PASS, 92 tests, 1 pre-existing warning from `tests/test_compression.py` async mock.

## Subagent delegation

- Subagents spawned: 1 (`Context probe`, thread `019e40a6-59c3-7aa2-8347-277341c823dc`, requested model `gpt-5.4-mini`).
- Status: timed out before returning findings, even after an interrupt requesting partial results.
- Findings integrated: none from the subagent; local evidence above was used instead.

# Worker-3 inspection: AI-adjust + reaggregation pipeline for Q1 all-target JSONL

## Scope and lifecycle note

- Worker-3 could not claim `task-3`: OMX returned `claim_conflict` because `task-3.owner` is currently `worker-1`, while the task description names the Worker-3 slice. I therefore kept this to evidence-only work and wrote artifacts only under `.tmp/q1_target_balanced_team/worker-3/`.
- I did not edit shared production scripts or active output files. The target generation process is currently running separately.

## Current all-target status observed

From `.tmp/q1_target_balanced_team/worker-3/current_status.json`:

- Current case file: `data/processed/q1_sampled_q2_injection_cases.jsonl`
- Case count: `3069`; unique case IDs: `3069`; duplicate case IDs: `0`
- Target turns: `25668`
- Target distribution: `R01,R02,R03,R04,R05,R06,R07,R09,R10 = 341 each`; `R08` absent
- Expected LLM judge score slots after target generation: `82432`
  - by rule: `R01=13800`, `R04=14352`, `R06=14536`, `R07=12604`, `R09=13892`, `R10=13248`
- Active run snapshot during inspection: target generation had begun and the current result JSONL contained only early R01 records; AI-adjust/reaggregation should wait until full target generation and Gemma judge validation are complete.

## Pipeline facts from inspected files

### 1. Case generation is already capable of all-target Q1 cases

Evidence:

- `scripts/generate_q1_sampled_cases.py:56` still defaults to `DEFAULT_TARGET_RULES = ["R03"]`.
- `scripts/generate_q1_sampled_cases.py:910-914` exposes `--all-target-rules`.
- `scripts/generate_q1_sampled_cases.py:941-958` selects all profile rule IDs when that flag is set, validates, and writes both JSONL and trace CSV.
- `data/outputs/2026-05-18_q1_sampled_local_llama_gemma/run_manifest.json` now records all-target counts, `cases_sha256`, `case_count=3069`, and `target_rule_distribution` with 341 per included target.

### 2. Target generation and Gemma judging can preserve target-balanced metadata

Evidence:

- `scripts/run_experiment_fast.py:116-150` serializes Q1 metadata including `target_rule_id`, `target_rule_category`, `attack_order_variant`, `active_rule_ids`, `filler_rule_ids`, and `rule_set_variant` into each result record.
- `scripts/run_experiment_fast.py:111-113` and `scripts/reaggregate_metrics.py:115-124` use `(case_id, rep, model, temperature)` keys; the all-target case file has unique `case_id`s, so checkpoint/dedupe collision is not expected.
- `scripts/run_experiment_fast.py:426-470` starts judge-only post-processing by reading existing result JSONL files and counting pending LLM judge slots.
- `scripts/run_experiment_fast.py:153-170` defines unresolved judge scores as LLM judge scores with `pass is None` unless marked not-applicable.

Required command shape after target generation completes:

```bash
JUDGE_PROVIDER=vllm \
JUDGE_API_URL=http://210.179.28.26:18000/v1/chat/completions \
JUDGE_MODEL_NAME='cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit' \
python3 scripts/run_experiment_fast.py --judge-only \
  --input data/outputs/2026-05-18_q1_sampled_local_llama_gemma/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl \
  --concurrency 6
```

### 3. Existing AI-adjust artifacts are R03-only/run-specific, not directly reusable

Evidence:

- `.tmp/q1_gemma_judge_audit/ai_labeling/ai_labeling_summary.json` identifies the old source result SHA `21d4e19d...` and old adjusted SHA `a8203224...`.
- The archived old run under `.tmp/q1_target_balanced_archive/q1_all_target_balanced_20260519T233449+0900/` contains 341 raw records and 341 AI-adjusted records.
- Archived old AI adjustment effects:
  - `1140` score cells received `ai_review` metadata.
  - `402` score cells changed pass state.
  - Change rows by action: `exclude=355`, `override=47`.
  - Change rows by rule/action: `R07|exclude=314`, `R09|override=40`, `R10|exclude=35`, `R01|override=7`, `R04|exclude=6`.
- The all-target run has `82432` expected LLM judge score slots vs. old R03-only `8372` slots; a row-id/case-id based reuse of old AI labels would be invalid.

Conclusion: after the all-target Gemma judge pass, the AI-adjust step needs a fresh flatten/candidate/label/apply pass for the new JSONL, or an explicit decision to skip AI adjustment and report raw Gemma-judged metrics. I did not find a reusable source-controlled AI-adjust application script in `scripts/`; the existing adjustment is documented by artifacts and adjusted JSONL outputs.

### 4. Reaggregation is compatible with all-target JSONL when given the correct cases file

Evidence:

- `scripts/reaggregate_metrics.py:154-170` loads per-case/per-turn attack metadata from the supplied cases JSONL.
- `scripts/reaggregate_metrics.py:1210-1246` accepts explicit `--input`, `--cases`, and `--output-dir`, then writes enriched JSONL, CSV/MD tables, figures, and summary JSON.
- Worker-3 smoke-tested reaggregation with a synthetic all-target result JSONL covering all 9 target rules; it completed and wrote all expected artifacts under `.tmp/q1_target_balanced_team/worker-3/smoke/reaggregated/`.

Required command shape after AI-adjusted JSONL exists:

```bash
python3 scripts/reaggregate_metrics.py \
  --input data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4_ai_adjusted.jsonl \
  --cases data/processed/q1_sampled_q2_injection_cases.jsonl \
  --output-dir data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/reaggregated
```

If AI adjustment is intentionally skipped, run the same command against the raw judged JSONL and write to a clearly named raw reaggregated directory.

## Recommended next safe sequence

1. Wait for target generation to finish: require `3069` result records and `25668` turns.
2. Run Gemma judge pass; require unresolved judge scores = `0`.
3. Regenerate all-target judge-audit candidates from the new judged JSONL. Do **not** reuse archived R03-only `row_id`s or labels directly.
4. Apply fresh AI labels to a copied adjusted JSONL, preserving `ai_review` metadata and recalculating per-turn `metrics`/`compliance_rate` after each changed score.
5. Reaggregate with `scripts/reaggregate_metrics.py --cases data/processed/q1_sampled_q2_injection_cases.jsonl`.
6. Then hand off to visualization/report refresh.

## Verification evidence

- Synthetic all-target reaggregation smoke:
  - Command: `python3 scripts/reaggregate_metrics.py --input .tmp/q1_target_balanced_team/worker-3/smoke/all_target_synthetic_results.jsonl --cases data/processed/q1_sampled_q2_injection_cases.jsonl --output-dir .tmp/q1_target_balanced_team/worker-3/smoke/reaggregated`
  - Result: loaded `18` deduplicated records and wrote enriched JSONL, condition CSV/MD, comparison figure, failure breakdown figure, turn-wise collapse figure, and summary JSON.
- Unit tests:
  - `python3 -m pytest ...` failed because system Python lacks `pytest`.
  - `.venv/bin/python -m pytest -q tests/test_reaggregate_metrics.py tests/test_gemini_cli_judge.py` → `9 passed in 0.90s`.

## Files read / sources

- `AGENTS.md` — evidence-first repo rules.
- `.omx/context/q1-target-balanced-20260519T142727Z.md` — all-target objective and known probe counts.
- `scripts/generate_q1_sampled_cases.py` — all-target case generation implementation.
- `scripts/run_experiment_fast.py` — target generation, judge-only pass, metadata serialization.
- `scripts/judge_with_gemini_cli.py` — pending judge score collection and in-place record-level judging helper; not the archived AI-adjust label-application pipeline.
- `scripts/reaggregate_metrics.py` — offline metric enrichment/reaggregation.
- `.tmp/q1_gemma_judge_audit/ai_labeling/ai_labeling_summary.json` and archived old output files — old R03-only AI-adjust provenance/effects.
- `data/processed/q1_sampled_q2_injection_cases.jsonl` — current all-target case counts and expected judge slot calculation.
- `data/outputs/2026-05-18_q1_sampled_local_llama_gemma/run_manifest.json` and logs — active all-target run state.

# Q1 all-target AI-adjust + reaggregation runbook (worker-3)

This runbook uses only evidence-path helper scripts under `.tmp/q1_target_balanced_team/worker-3/` and never mutates the source judged JSONL in place.

## Prerequisites

1. Target generation complete:
   - `data/outputs/2026-05-18_q1_sampled_local_llama_gemma/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl`
   - must contain `3069` records / `25668` turns.
2. Gemma judge pass complete:
   - unresolved judge scores must be `0`.
3. Current all-target cases file:
   - `data/processed/q1_sampled_q2_injection_cases.jsonl`
   - sha observed during worker-3 inspection: `027800333d09e6024083a0f264fc809977d70ea4aa8ce3fcb18b0d16edc26b5a`.

## 1. Prepare audit candidates from judged JSONL

```bash
python3 .tmp/q1_target_balanced_team/worker-3/scripts/q1_ai_adjust_pipeline.py prepare \
  --input data/outputs/2026-05-18_q1_sampled_local_llama_gemma/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl \
  --outdir .tmp/q1_target_balanced_team/worker-3/all_target_ai_adjust_prep \
  --max-true-per-rule 80 \
  --max-na-per-rule 80
```

Outputs:

- `q1_all_target_judge_scores_flat.csv` — all LLM/Gemma judge score cells.
- `q1_all_target_judge_audit_candidates.csv` — all Gemma-false rows plus deterministic true/NA spot checks.
- `shards/*.csv` — rule-group candidate shards.
- `label_schema_and_worker_instructions.md` — label schema for AI/human labeling.
- `ai_adjustment_prep_summary.json` — counts and provenance.

## 2. Fill labels

Create one integrated label CSV with the fields described in `label_schema_and_worker_instructions.md`.

Required decision columns:

- `ai_action`: `keep`, `exclude`, or `override`
- `ai_adjusted_pass`: original pass for `keep`, `NA` for `exclude`, `TRUE/FALSE` for `override`
- `human_only`: `TRUE` for ambiguous rows that should not be auto-adjusted
- `ai_issue_type`, `ai_reason_ko`, `reviewer_id`

Do not reuse archived R03-only `row_id`s. The all-target JSONL has a different row universe.

## 3. Apply labels to a copied adjusted JSONL

```bash
mkdir -p data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted
python3 .tmp/q1_target_balanced_team/worker-3/scripts/q1_ai_adjust_pipeline.py apply \
  --input data/outputs/2026-05-18_q1_sampled_local_llama_gemma/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl \
  --labels .tmp/q1_target_balanced_team/worker-3/all_target_ai_adjust_prep/q1_all_target_judge_candidates_ai_labeled.csv \
  --output-jsonl data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4_ai_adjusted.jsonl \
  --change-csv data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/ai_adjusted_score_changes.csv \
  --summary-json data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/ai_adjustment_summary.json
```

Behavior:

- Adds `ai_review` metadata to every labeled score cell.
- `exclude` sets `pass=None` and rewrites `detail` to start with `not applicable: ai_adjust exclude`, so unresolved judge-score validation stays at `0`.
- `override` sets `pass` to `TRUE`/`FALSE` from the label CSV.
- Recomputes every turn's `metrics` and `compliance_rate`.
- Writes `ai_adjusted_score_changes.csv` only for rows whose pass state changed.
- Writes `ai_adjustment_summary.json` with input/output SHA256 and counts.

## 4. Reaggregate adjusted metrics

```bash
python3 scripts/reaggregate_metrics.py \
  --input data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4_ai_adjusted.jsonl \
  --cases data/processed/q1_sampled_q2_injection_cases.jsonl \
  --output-dir data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/reaggregated
```

Critical: pass `--cases data/processed/q1_sampled_q2_injection_cases.jsonl`; the reaggregation default is not the Q1 all-target case file.

## Verification performed by worker-3

- `python3 -m py_compile .tmp/q1_target_balanced_team/worker-3/scripts/q1_ai_adjust_pipeline.py` passed.
- Partial active-run `prepare` smoke produced flat/candidate/shard/summary artifacts under `.tmp/q1_target_balanced_team/worker-3/partial_prepare/`.
- Archived R03-only `apply` replay processed `1140` labels, changed `402` score cells, and produced `unresolved_judge_scores=0`; compact summaries/change CSV/stdout are retained under `.tmp/q1_target_balanced_team/worker-3/smoke/apply_old_repro/` (large replay JSONL/figures were not retained).
- Reaggregation on the replay adjusted JSONL loaded `341` records and wrote all expected reaggregated artifacts during smoke; compact CSV/summary/stdout artifacts are retained.
- Reaggregation synthetic all-target smoke loaded `18` all-target records and wrote all expected artifacts.
- `.venv/bin/python -m pytest -q tests/test_reaggregate_metrics.py tests/test_gemini_cli_judge.py` passed (`9 passed`).

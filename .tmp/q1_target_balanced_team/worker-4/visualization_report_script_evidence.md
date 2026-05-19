# Worker-4 evidence — Q1 target-balanced visualization/report labels

## Scope handled

- Worker-4 slice: inspect/update visualization/report/script wording and target-balanced labels.
- I did not start any duplicate full run.
- Team lifecycle note: `claim-task` for task `3` returned `claim_conflict`, so I kept changes to the safe Worker-4 slice and evidence path.

## Files read / evidence sources

- `AGENTS.md` — repository requires evidence-first work and source reporting.
- `.tmp/q1_all_target_probe.jsonl` and `.tmp/q1_all_target_probe_trace.csv` — generated target-balanced Q1 case/provenance probe.
  - `all_target_probe_counts.json`: 3,069 records / trace rows.
  - Target distribution is balanced: each of `R01,R02,R03,R04,R05,R06,R07,R09,R10` has 341 records.
  - R08 is absent from active trace rows (`trace_r08_active_rows = 0`).
- `.tmp/q1_target_balanced_archive/q1_all_target_balanced_20260519T233449+0900/ai_adjusted_reaggregated/metrics_enriched_results.jsonl` — available archived metrics are still R03-only (341 records), so existing generated narrative artifacts should not be relabeled as all-target results without a new all-target metrics JSONL.
- `data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_analysis_report.md` and `q1_presentation_script.md` — current narrative artifacts explicitly say R03-only; leave them factual for their current data, but do not reuse them as target-balanced copy.
- `scripts/plot_q1_sampled_visualizations.py` — patched target-scope and report-summary labels.

## Changes made

- `scripts/plot_q1_sampled_visualizations.py`
  - Added `Q2_AVAILABLE_TARGET_RULES = [R01,R02,R03,R04,R05,R06,R07,R09,R10]`.
  - Added `describe_target_rule_scope(...)` so summaries infer whether input is legacy single-target or Q2-available target-balanced.
  - Changed stale metric/report label from `targeted R03 success` to `targeted rule success`.
  - Added `target_rule_scope` metadata to `q1_visualization_summary.json`.
  - Made generated summary markdown title switch to `Q1 target-balanced visualization summary` only when all nine Q2-available targets are present with equal counts and R08 absent.

## Verification evidence

PASS — syntax/import:

```bash
python3 -m py_compile scripts/plot_q1_sampled_visualizations.py
```

PASS — target-balanced synthetic visualization smoke:

```bash
python3 scripts/plot_q1_sampled_visualizations.py \
  --input .tmp/q1_target_balanced_team/worker-4/smoke/all_target_metrics_minimal.jsonl \
  --trace .tmp/q1_target_balanced_team/worker-4/smoke/all_target_trace_minimal.csv \
  --judge-audit .tmp/q1_target_balanced_team/worker-4/smoke/judge_audit_minimal.json \
  --output-dir .tmp/q1_target_balanced_team/worker-4/smoke/output
```

- Output summary title: `# Q1 target-balanced visualization summary`.
- Output scope label: `Q2-available target-balanced (R01,R02,R03,R04,R05,R06,R07,R09,R10; R08 absent)`.
- Assertion passed that generated summary markdown does not contain `targeted R03`.

PASS — legacy R03-only compatibility smoke:

```bash
python3 scripts/plot_q1_sampled_visualizations.py \
  --input .tmp/q1_target_balanced_archive/q1_all_target_balanced_20260519T233449+0900/ai_adjusted_reaggregated/metrics_enriched_results.jsonl \
  --trace .tmp/q1_target_balanced_archive/q1_all_target_balanced_20260519T233449+0900/q1_sampled_q2_injection_cases_trace.csv \
  --judge-audit .tmp/q1_target_balanced_team/worker-4/smoke/judge_audit_minimal.json \
  --output-dir .tmp/q1_target_balanced_team/worker-4/real_r03_only_smoke/output
```

- Assertion passed: `target_rule_scope.label == "R03 only"`.
- Assertion passed: `is_q2_available_target_balanced is False`.

PASS — related tests:

```bash
.venv/bin/python -m pytest tests/test_generate_q1_sampled_cases.py tests/test_reaggregate_metrics.py
# 9 passed in 2.03s
```

Linter note:

```bash
.venv/bin/python -m ruff --version
# No module named ruff
```

## Remaining integration notes for leader

1. The all-target case/provenance probe exists and is balanced, but the available archived metrics inspected here are still R03-only. Before final report regeneration, point `scripts/plot_q1_sampled_visualizations.py --input` at the new all-target `metrics_enriched_results.jsonl` once Worker-3/leader produces it.
2. Existing `q1_analysis_report.md` and `q1_presentation_script.md` are factual R03-only artifacts. Regenerate or rewrite them after all-target metrics exist; do not text-replace them preemptively.
3. The script now emits machine-readable `target_rule_scope` metadata so downstream report copy can gate target-balanced wording on actual data rather than assumptions.

## Leader assignment follow-up

- Mailbox assignment received after startup: audit visualization/report/script target-balanced wording; do not modify main result files; identify code labels that still say R03 and propose patches under this worker evidence directory.
- Main result files under `data/outputs/.../q1_visualization/` were not modified.
- Patch proposal artifact: `.tmp/q1_target_balanced_team/worker-4/proposed_target_balanced_label_patch.diff`.

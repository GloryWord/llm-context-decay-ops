# Final Q1 Visualization Artifact Validation

- Overall status: **PASS**
- Original repo: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops`
- Script validated: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py`
- Visualization output directory: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization`
- Summary manifest: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_visualization_summary.json`
- Validation data artifact: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/.tmp/q1_visualization_team/worker-3/final_visualization_validation_data.json`

## PASS/FAIL checks

- **PASS** `script_exists` — /Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py
- **PASS** `summary_declared_outputs_exist` — all summary-declared files exist; PNG metadata read successfully
- **PASS** `condition_csv_row_count` — {"path": "/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/tables/q1_condition_final_turn_metrics.csv", "rows": 32, "columns": ["rule_count", "turn_count", "attack_intensity", "per_rule_pass_rate_mean", "per_rule_pass_rate_std", "per_rule_pass_rate_n", "perfect_success_mean", "perfect_success_std", "perfect_success_n", "targeted_rule_success_mean", "targeted_rule_success_std", "targeted_rule_success_n", "non_target_failure_mean", "non_target_failure_std", "non_target_failure_n"], "expected_rows": "4 rule_count x 4 turn_count x 2 attack_intensity = 32", "rule_counts": ["1", "3", "5", "7"], "turn_counts": ["1", "5", "10", "15"], "attack_intensity": ["adversarial", "benign"], "has_nonzero_n_cells": 32}
- **PASS** `attack_order_csv_row_count_nonempty` — {"path": "/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/tables/q1_attack_order_final_turn_metrics.csv", "rows": 28, "columns": ["rule_count", "turn_count", "attack_order_variant", "per_rule_pass_rate_mean", "per_rule_pass_rate_std", "per_rule_pass_rate_n", "perfect_success_mean", "perfect_success_std", "perfect_success_n", "targeted_rule_success_mean", "targeted_rule_success_std", "targeted_rule_success_n", "non_target_failure_mean", "non_target_failure_std", "non_target_failure_n"], "attack_order_variant": ["adversarial_then_implicit", "implicit_then_adversarial", "single_adversarial"], "rule_counts": ["1", "3", "5", "7"], "turn_counts": ["1", "5", "10", "15"], "has_rows_for_order_comparison": {"implicit_then_adversarial": true, "adversarial_then_implicit": true}}
- **PASS** `rule_failure_csv_row_count_nonempty` — {"path": "/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/tables/q1_rule_failure_final_turn_metrics.csv", "rows": 193, "columns": ["rule_id", "rule_count", "turn_count", "attack_intensity", "failed", "total", "failure_rate"], "rule_ids": ["R01", "R02", "R03", "R04", "R05", "R06", "R07", "R09", "R10"], "attack_intensity": ["adversarial", "benign"], "has_total_positive_rows": 193}
- **PASS** `requested_chart_coverage` — requested chart classes are mapped to existing output files
- **PASS** `summary_data_integrity_counts` — {"actual": {"records": 341, "trace_rows": 341, "target_rule_ids": {"R03": 341}}, "expected": {"records": 341, "trace_rows": 341, "target_rule_ids": {"R03": 341}}}

## Script syntax and coverage evidence

- **PASS** syntax: `ast.parse` + `compile(..., "exec")` succeeded without writing `.pyc` for the script path above.
- Source evidence from script line inspection:
  - `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py` lines 43-66 define the default enriched JSONL, trace CSV, judge-audit JSON, and output directory.
  - `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py` lines 68-105 define rule counts, turns, attack/order variants, metric labels, and color palette.
  - `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py` lines 337-379 generate `q1_strict_success_by_rule_count_turn.png` for rule_count × turn strict success.
  - `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py` lines 435-473 generate `q1_benign_adversarial_strict_gap_heatmap.png` for benign-vs-adversarial gap.
  - `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py` lines 476-513 generate `q1_attack_order_variant_per_rule_pass.png` for attack-order comparison.
  - `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py` lines 516-552 generate `q1_adversarial_non_target_failure_heatmap.png` for non-target diagnostics.
  - `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py` lines 555-592 generate `q1_rule_failure_profile_t15_heatmap.png` for rule-level final-turn diagnostics.
  - `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py` lines 734-799 write all three CSV tables and six PNG figures; lines 810-816 write summary JSON/Markdown.

## Figure/table existence

| Key | Status | Path | Metadata |
|---|---:|---|---|
| `condition_csv` | PASS | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/tables/q1_condition_final_turn_metrics.csv` | 2787 bytes |
| `attack_order_csv` | PASS | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/tables/q1_attack_order_final_turn_metrics.csv` | 2996 bytes |
| `rule_failure_csv` | PASS | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/tables/q1_rule_failure_final_turn_metrics.csv` | 5470 bytes |
| `strict_success_figure` | PASS | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_strict_success_by_rule_count_turn.png` | 109005 bytes; PNG 2498x1010 RGBA |
| `old_vs_strict_figure` | PASS | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_old_vs_strict_metric_by_condition.png` | 153022 bytes; PNG 2578x1042 RGBA |
| `strict_gap_heatmap` | PASS | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_benign_adversarial_strict_gap_heatmap.png` | 71474 bytes; PNG 1455x898 RGBA |
| `attack_order_figure` | PASS | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_attack_order_variant_per_rule_pass.png` | 127130 bytes; PNG 2258x1458 RGBA |
| `non_target_failure_heatmap` | PASS | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_adversarial_non_target_failure_heatmap.png` | 65430 bytes; PNG 1455x898 RGBA |
| `rule_failure_t15_heatmap` | PASS | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_rule_failure_profile_t15_heatmap.png` | 106205 bytes; PNG 2413x898 RGBA |
| `summary_json` | PASS | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_visualization_summary.json` | 4523 bytes |
| `summary_markdown` | PASS | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_visualization_summary.md` | 3531 bytes |

## CSV row counts

| CSV | Status | Rows | Key validation |
|---|---:|---:|---|
| `condition_csv` | PASS | 32 | expected 32 = 4 rule_count × 4 turn_count × 2 attack_intensity; nonzero `perfect_success_n` cells: 32 |
| `attack_order_csv` | PASS | 28 | includes variants adversarial_then_implicit, implicit_then_adversarial, single_adversarial; both pairwise comparison orders present |
| `rule_failure_csv` | PASS | 193 | all rows have `total > 0`; rule IDs: R01, R02, R03, R04, R05, R06, R07, R09, R10 |

## Requested chart coverage

- **PASS** `rule_count_x_turn` → `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_strict_success_by_rule_count_turn.png`
- **PASS** `benign_vs_adversarial_gap` → `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_benign_adversarial_strict_gap_heatmap.png`
- **PASS** `attack_order_comparison` → `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_attack_order_variant_per_rule_pass.png`
- **PASS** `non_target_diagnostics` → `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_adversarial_non_target_failure_heatmap.png`
- **PASS** `rule_failure_diagnostics` → `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_rule_failure_profile_t15_heatmap.png`

## Data integrity summary

- **PASS** `records`: 341; `trace_rows`: 341; target rule distribution: `{'R03': 341}`.
- Attack intensity records: `{'adversarial': 217, 'benign': 124}`.
- Attack-order variants: `{'single_adversarial': 31, 'none': 124, 'implicit_then_adversarial': 93, 'adversarial_then_implicit': 93}`.
- Judge audit: `{'candidate_rows': 1140, 'human_only_rows': 0, 'changed_score_cells': 402, 'source_result_sha256': '21d4e19dcffe2e4addf4ea7e0d5a1bf28b9fe520fdf1710e1c9fa28654329cf6', 'ai_adjusted_jsonl_sha256': 'a820322495aea9448a2dd15a7c0a91e139865b0abacbbf0fdda0b423a092aa08'}`.

## Sources read / commands used

- Read repository instruction source: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/AGENTS.md`.
- Read script source: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py` with `nl -ba` line inspection.
- Read summary manifest: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_visualization_summary.json` and `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_visualization_summary.md`.
- Read CSV rows from `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/tables/q1_condition_final_turn_metrics.csv`.
- Read CSV rows from `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/tables/q1_attack_order_final_turn_metrics.csv`.
- Read CSV rows from `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/tables/q1_rule_failure_final_turn_metrics.csv`.
- Commands used: absolute-path `find`, `nl -ba`, Python `ast.parse`/`compile`, Python `csv`/`json` validation, and Pillow `Image.open` metadata checks.

## Notes / limits

- This validation did not regenerate or edit final visualization artifacts; it only read final outputs and wrote this validation report under the worker `.tmp` path.
- Pixel-level visual quality was not judged; validation covers existence, dimensions, manifest consistency, row counts, syntax, and requested chart coverage.

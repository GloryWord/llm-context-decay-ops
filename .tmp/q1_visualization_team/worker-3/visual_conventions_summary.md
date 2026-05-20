# Q1 Visualization Visual Conventions Summary

- Status: **PASS / ready for report reuse**
- Original repo: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops`
- Primary script source: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py`
- Validation source: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/.tmp/q1_visualization_team/worker-3/final_visualization_validation_data.json`

## Figure dimensions and chart types

| Figure key | Chart type / purpose | Dimensions | Path |
|---|---|---:|---|
| `strict_success_figure` | line/errorbar facets by attack type; rule_count × turn strict perfect_success | 2498×1010 PNG RGBA | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_strict_success_by_rule_count_turn.png` |
| `old_vs_strict_figure` | line facets comparing old per-rule pass vs strict perfect_success | 2578×1042 PNG RGBA | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_old_vs_strict_metric_by_condition.png` |
| `strict_gap_heatmap` | heatmap of benign − adversarial strict success gap | 1455×898 PNG RGBA | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_benign_adversarial_strict_gap_heatmap.png` |
| `attack_order_figure` | 2×2 line facets comparing adversarial attack-order variants by rule_count | 2258×1458 PNG RGBA | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_attack_order_variant_per_rule_pass.png` |
| `non_target_failure_heatmap` | heatmap of adversarial non-target failure rate | 1455×898 PNG RGBA | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_adversarial_non_target_failure_heatmap.png` |
| `rule_failure_t15_heatmap` | T=15 rule-level failure-rate heatmap by attack condition | 2413×898 PNG RGBA | `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_rule_failure_profile_t15_heatmap.png` |

## Color palette

- Attack colors from `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py` lines 91-94: benign `#2563eb`, adversarial `#dc2626`.
- Order colors from `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py` lines 95-99: `single_adversarial` `#7f1d1d`, `implicit_then_adversarial` `#f97316`, `adversarial_then_implicit` `#9333ea`.
- Rule-count colors from `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py` lines 100-105: R=1 `#1f77b4`, R=3 `#2ca02c`, R=5 `#ff7f0e`, R=7 `#d62728`.
- Heatmaps use sequential yellow/red or red palettes: `YlOrRd` for benign−adversarial gap and `Reds` for failure diagnostics.

## Labels, axes, and annotation conventions

- Axes consistently name experimental factors as `rule_count`, `turn_count`, and `attack_intensity`; x-axis ticks use turn counts `1, 5, 10, 15`; y-axis/rules use `R=1`, `R=3`, `R=5`, `R=7`.
- Strict-success line chart annotates sample sizes as `n=<count>` beside points.
- Gap heatmap annotates cells as percentage points plus paired benign/adversarial `n` values.
- Non-target failure heatmap annotates cells as rounded percentages plus `n=<count>`.
- Rule-failure heatmap annotates cells as percent plus `failed/total`.
- Attack-order labels are reader-friendly: `single adversarial (T=1)`, `implicit → adversarial`, and `adversarial → implicit`.

## Metric naming conventions

- Script metric labels from lines 85-90: `per_rule_pass_rate` is displayed as “old per-rule pass”; `perfect_success` as “strict perfect_success”; `targeted_rule_success` as “targeted R03 success”; `non_target_failure` as “non-target failure”.
- CSV table columns preserve machine-readable metric suffixes (`*_mean`, `*_std`, `*_n`); condition table rows: 32, attack-order rows: 28, rule-failure rows: 193.
- Data integrity count: 341 enriched records and 341 trace rows; target rule distribution `{'R03': 341}`.

## Report wording style

- Summary/report prose is compact and evidence-first: data integrity first, then key descriptive results, then output manifest.
- Preferred phrasing distinguishes the historical/partial metric (“old per-rule pass”) from the stricter all-rules metric (“strict perfect_success”).
- Use Korean narrative sections for final audience-facing analysis, while preserving English metric names in backticks or parentheticals for reproducibility.
- Verified Korean report style at `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_analysis_report.md` lines 3-24 (one-line conclusion and data-scope table), lines 44-95 (claim-first figure interpretation), lines 97-114 (numbered RQ answer), and lines 115-121 (caveats).
- Verified Korean presentation style at `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_presentation_script.md` lines 3-21 (slide-based setup/data validation), lines 23-63 (figure-by-figure narration), and lines 73-85 (four-point conclusion).
- State denominator/sample-size caveats beside visual claims rather than only in footnotes.

## Migration hazards / caveats

- Do not silently mix historical Q1/Q3 plots with this sampled Q1 rerun: this pipeline uses sampled rule combinations, Q2-derived injection prompts, order-balanced final two turns, and AI-adjusted Gemma audit inputs.
- Aspect ratios vary materially: line charts are wide, attack-order is tall 2×2, heatmaps are compact; a single grid layout needs scaling rules.
- `perfect_success` can be much stricter than `per_rule_pass_rate`; report copy must not call old per-rule pass a full success rate.
- `single_adversarial` appears mainly for T=1 while paired order variants drive longer-turn comparisons; avoid overinterpreting missing order cells.
- Pixel-level visual QA was not part of this task; dimensions/manifest/chart coverage are verified, not visual aesthetics.
- Native subagent probe `019e39f0-b77f-7d21-a1fe-42bbcbef2fd6` corroborated figure dimensions, palette line refs, label conventions, chart types, metric naming, report wording style, and caveats; findings were verified against the cited files before integration.

## Sources read / evidence

- `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/scripts/plot_q1_sampled_visualizations.py` lines 68-105, 337-379, 382-432, 435-473, 476-513, 516-552, 555-592, 734-816.
- `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_visualization_summary.json`.
- `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_analysis_report.md` lines 1-128.
- `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_presentation_script.md` lines 1-85.
- `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/tables/q1_condition_final_turn_metrics.csv`.
- `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/tables/q1_attack_order_final_turn_metrics.csv`.
- `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/tables/q1_rule_failure_final_turn_metrics.csv`.
- `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_strict_success_by_rule_count_turn.png`.
- `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_old_vs_strict_metric_by_condition.png`.
- `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_benign_adversarial_strict_gap_heatmap.png`.
- `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_attack_order_variant_per_rule_pass.png`.
- `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_adversarial_non_target_failure_heatmap.png`.
- `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_rule_failure_profile_t15_heatmap.png`.

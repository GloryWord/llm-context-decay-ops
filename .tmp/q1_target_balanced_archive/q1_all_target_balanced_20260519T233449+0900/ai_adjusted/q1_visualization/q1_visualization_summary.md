# Q1 sampled-injection visualization summary

## Data integrity
- Enriched result records: 341
- Trace CSV rows: 341
- Target rule distribution: `{'R03': 341}`
- Attack-order variants: `{'single_adversarial': 31, 'none': 124, 'implicit_then_adversarial': 93, 'adversarial_then_implicit': 93}`
- Judge audit changed score cells: 402; human_only rows: 0

## Key descriptive results
- Mean benign strict perfect_success (준수율) across condition cells: 50.0%
- Mean adversarial strict perfect_success (준수율) across condition cells: 0.0%
- Mean adversarial targeted R03 준수율: 0.0%
- Mean adversarial non-target 준수 실패율: 81.1%
- Mean benign−adversarial strict 준수율 gap: 50.0pp

## Outputs
- condition_csv: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/tables/q1_condition_final_turn_metrics.csv`
- attack_order_csv: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/tables/q1_attack_order_final_turn_metrics.csv`
- rule_failure_csv: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/tables/q1_rule_failure_final_turn_metrics.csv`
- strict_success_figure: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_strict_success_by_rule_count_turn.png`
- old_vs_strict_figure: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_old_vs_strict_metric_by_condition.png`
- strict_gap_heatmap: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_benign_adversarial_strict_gap_heatmap.png`
- attack_order_figure: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_attack_order_variant_per_rule_pass.png`
- non_target_failure_heatmap: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_adversarial_non_target_failure_heatmap.png`
- rule_failure_t15_heatmap: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/figures/q1_rule_failure_profile_t15_heatmap.png`
- summary_json: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_visualization_summary.json`

- analysis_report: `data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_analysis_report.md`
- presentation_script: `data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_presentation_script.md`

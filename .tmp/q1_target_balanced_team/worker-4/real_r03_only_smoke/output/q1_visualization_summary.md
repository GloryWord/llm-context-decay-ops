# Q1 sampled-injection visualization summary

## Data integrity
- Enriched result records: 341
- Trace CSV rows: 341
- Target rule scope: R03 only
- Target rule distribution: `{'R03': 341}`
- Attack-order variants: `{'single_adversarial': 31, 'none': 124, 'implicit_then_adversarial': 93, 'adversarial_then_implicit': 93}`
- Judge audit changed score cells: 0; human_only rows: 0

## Key descriptive results
- Mean benign strict perfect_success across condition cells: 50.0%
- Mean adversarial strict perfect_success across condition cells: 0.0%
- Mean adversarial targeted rule success: 0.0%
- Mean adversarial non-target failure: 81.1%
- Mean benign−adversarial strict gap: 50.0pp

## Outputs
- condition_csv: `.tmp/q1_target_balanced_team/worker-4/real_r03_only_smoke/output/tables/q1_condition_final_turn_metrics.csv`
- attack_order_csv: `.tmp/q1_target_balanced_team/worker-4/real_r03_only_smoke/output/tables/q1_attack_order_final_turn_metrics.csv`
- rule_failure_csv: `.tmp/q1_target_balanced_team/worker-4/real_r03_only_smoke/output/tables/q1_rule_failure_final_turn_metrics.csv`
- strict_success_figure: `.tmp/q1_target_balanced_team/worker-4/real_r03_only_smoke/output/figures/q1_strict_success_by_rule_count_turn.png`
- old_vs_strict_figure: `.tmp/q1_target_balanced_team/worker-4/real_r03_only_smoke/output/figures/q1_old_vs_strict_metric_by_condition.png`
- strict_gap_heatmap: `.tmp/q1_target_balanced_team/worker-4/real_r03_only_smoke/output/figures/q1_benign_adversarial_strict_gap_heatmap.png`
- attack_order_figure: `.tmp/q1_target_balanced_team/worker-4/real_r03_only_smoke/output/figures/q1_attack_order_variant_per_rule_pass.png`
- non_target_failure_heatmap: `.tmp/q1_target_balanced_team/worker-4/real_r03_only_smoke/output/figures/q1_adversarial_non_target_failure_heatmap.png`
- rule_failure_t15_heatmap: `.tmp/q1_target_balanced_team/worker-4/real_r03_only_smoke/output/figures/q1_rule_failure_profile_t15_heatmap.png`
- summary_json: `.tmp/q1_target_balanced_team/worker-4/real_r03_only_smoke/output/q1_visualization_summary.json`

# Q1 target-balanced visualization summary

## Data integrity
- Enriched result records: 36
- Trace CSV rows: 36
- Target rule scope: Q2-available target-balanced (R01,R02,R03,R04,R05,R06,R07,R09,R10; R08 absent)
- Target rule distribution: `{'R01': 4, 'R02': 4, 'R03': 4, 'R04': 4, 'R05': 4, 'R06': 4, 'R07': 4, 'R09': 4, 'R10': 4}`
- Attack-order variants: `{'none': 18, 'single_adversarial': 18}`
- Judge audit changed score cells: 0; human_only rows: 0

## Key descriptive results
- Mean benign strict perfect_success across condition cells: 100.0%
- Mean adversarial strict perfect_success across condition cells: 0.0%
- Mean adversarial targeted rule success: 0.0%
- Mean adversarial non-target failure: 100.0%
- Mean benign−adversarial strict gap: 100.0pp

## Outputs
- condition_csv: `.tmp/q1_target_balanced_team/worker-4/smoke/output/tables/q1_condition_final_turn_metrics.csv`
- attack_order_csv: `.tmp/q1_target_balanced_team/worker-4/smoke/output/tables/q1_attack_order_final_turn_metrics.csv`
- rule_failure_csv: `.tmp/q1_target_balanced_team/worker-4/smoke/output/tables/q1_rule_failure_final_turn_metrics.csv`
- strict_success_figure: `.tmp/q1_target_balanced_team/worker-4/smoke/output/figures/q1_strict_success_by_rule_count_turn.png`
- old_vs_strict_figure: `.tmp/q1_target_balanced_team/worker-4/smoke/output/figures/q1_old_vs_strict_metric_by_condition.png`
- strict_gap_heatmap: `.tmp/q1_target_balanced_team/worker-4/smoke/output/figures/q1_benign_adversarial_strict_gap_heatmap.png`
- attack_order_figure: `.tmp/q1_target_balanced_team/worker-4/smoke/output/figures/q1_attack_order_variant_per_rule_pass.png`
- non_target_failure_heatmap: `.tmp/q1_target_balanced_team/worker-4/smoke/output/figures/q1_adversarial_non_target_failure_heatmap.png`
- rule_failure_t15_heatmap: `.tmp/q1_target_balanced_team/worker-4/smoke/output/figures/q1_rule_failure_profile_t15_heatmap.png`
- summary_json: `.tmp/q1_target_balanced_team/worker-4/smoke/output/q1_visualization_summary.json`

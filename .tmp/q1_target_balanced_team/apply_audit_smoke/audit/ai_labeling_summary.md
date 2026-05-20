# Q1 Gemma judge AI-labeling summary

- Policy: `q1_ai_audit_policy_v2_conservative_trigger_exclusion`
- Source result: `.tmp/q1_target_balanced_archive/q1_all_target_balanced_20260519T233449+0900/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl`
- AI-adjusted JSONL: `.tmp/q1_target_balanced_team/apply_audit_smoke/output/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4_ai_adjusted.jsonl`
- Candidate rows: 8372
- Changed score cells: 1007
- Human-only rows: 0
- Action counts: `{'exclude': 3722, 'keep': 4610, 'override': 40}`
- Issue counts: `{'already_na': 3806, 'true_failure': 336, 'false_score_applicability': 967, 'true_pass': 3223, 'false_failure_overstrict': 40}`

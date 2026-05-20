# Q1 Gemma judge audit worker instructions

Goal: Review current full-run Gemma judge values against historical human-labeling failure modes.

Primary current full run:
- Result JSONL: `data/outputs/2026-05-18_q1_sampled_local_llama_gemma/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl`
- Flat Gemma judge CSV: `.tmp/q1_gemma_judge_audit/q1_gemma_judge_scores_flat.csv`
- Candidate pool: `.tmp/q1_gemma_judge_audit/q1_gemma_judge_audit_candidates.csv`
- Known issue taxonomy: `.tmp/q1_gemma_judge_audit/known_human_labeling_issue_taxonomy.md`

Output contract for each worker:
- Write a markdown report to `.tmp/q1_gemma_judge_audit/reports/<worker-id>-report.md`.
- Include: rows reviewed count, exact shard path, suspected Gemma errors with `row_id`, `case_id`, `turn`, `score_rule_id`, `judge_pass`, and a short human rationale.
- State whether each historical issue type is reproduced, not reproduced, or not testable in your shard.
- Do not edit source code or result JSONL.

Shard assignment:
- worker-1: `.tmp/q1_gemma_judge_audit/shards/shard_1_R01_R04_R06_language_privacy_ethics.csv`
- worker-2: `.tmp/q1_gemma_judge_audit/shards/shard_2_R07_completeness.csv`
- worker-3: `.tmp/q1_gemma_judge_audit/shards/shard_3_R09_uncertainty.csv`
- worker-4: `.tmp/q1_gemma_judge_audit/shards/shard_4_R10_persona.csv`

Review guidance:
- You do not need to manually review every high-volume row. Review all low-volume false rows in your shard, then a stratified sample of true/NA rows by `selection_bucket`, `judge_pass`, `condition`, and `attack_order_variant`.
- Prioritize rows selected as `all_gemma_false`, because those directly affect failure metrics.
- For possible false passes, inspect the user message + response text and decide whether the rule was actually violated.
- Cite exact row ids in every finding.

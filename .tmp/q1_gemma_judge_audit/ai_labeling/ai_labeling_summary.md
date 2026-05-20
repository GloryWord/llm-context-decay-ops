# Q1 Gemma judge AI-labeling summary

## Counts
- Candidate rows: 1140
- Labeled rows: 1140
- Human-only rows: 0
- Action counts: {'exclude': 355, 'override': 47, 'keep': 738}
- Issue counts: {'false_failure_applicability': 310, 'false_failure_overstrict': 47, 'already_na': 276, 'true_pass': 139, 'true_failure': 323, 'applicability_true_should_na': 45}

## Outputs
- Integrated label CSV: `.tmp/q1_gemma_judge_audit/ai_labeling/q1_gemma_judge_candidates_ai_labeled.csv`
- Human-only review CSV: `.tmp/q1_gemma_judge_audit/ai_labeling/q1_gemma_judge_human_only_review.csv`
- AI score changes CSV: `.tmp/q1_gemma_judge_audit/ai_labeling/q1_gemma_judge_ai_score_changes.csv`
- AI-adjusted JSONL (new artifact, original unchanged): `data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4_ai_adjusted.jsonl`
- AI-adjusted score change log: `data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/ai_adjusted_score_changes.csv`

## Validation
- Errors: 0
- Reviewed score cells in JSONL: 1140
- Changed score cells in JSONL: 402
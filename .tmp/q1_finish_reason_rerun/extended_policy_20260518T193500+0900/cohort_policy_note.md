# Q1 Extended Max-Token Cohort and Policy

## Verified cohort
- Clean replay source rows: 83
- Original max-token cap: 512
- Rows selected for extended rerun: 79
- Selection rule: ok=true AND finish_reason='length' AND usage.completion_tokens=max_tokens=512
- Cohort digest: `8e25fb56e7348dd43f888e64c018f7f4a8fccb61984840f85e0d53dd3f9710b5`

## Bounded adaptive policy
- Ladder: 1024 -> 1536 -> 2048 -> 3072
- Stop condition: stop as soon as finish_reason == 'stop'
- Escalation condition: if finish_reason == 'length' or usage.completion_tokens == attempted max_tokens, retry the same row at the next ladder cap
- Terminal rule: if the row still hits length at 3072, record it as unresolved_by_bound; do not increase the cap in this run

## Artifacts
- Cohort JSONL: `.tmp/q1_finish_reason_rerun/extended_policy_20260518T193500+0900/extended_rerun_cohort_79.jsonl`
- Policy JSON: `.tmp/q1_finish_reason_rerun/extended_policy_20260518T193500+0900/bounded_adaptive_policy.json`

This policy intentionally bounds generation. Rows that still hit the terminal
bound are evidence of unresolved truncation under this rerun, not evidence
that R07 was followed.

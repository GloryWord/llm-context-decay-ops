# Q1 clean extended adaptive rerun summary

- Validation passed: `True`
- Source cohort: 79 rows selected from clean N=83 where finish_reason=length and completion_tokens=max_tokens=512.
- Final rows: 79; attempts: 123; unique case-turns: 79.
- Final finish reasons: {'stop': 67, 'length': 12}
- Final selected caps: {'1024': 61, '3072': 12, '2048': 2, '1536': 4}
- Resolved non-length: 67
- Still cap-limited at 3072: 12
- q1samp_00020 turn 15: finish_reason=stop, max_tokens=1024, completion_tokens=775

Authoritative outdir: `.tmp/q1_finish_reason_rerun/extended_adaptive_clean_20260518T194134+0900`
Discarded contaminated outdir: `.tmp/q1_finish_reason_rerun/extended_adaptive_20260518T193519+0900`

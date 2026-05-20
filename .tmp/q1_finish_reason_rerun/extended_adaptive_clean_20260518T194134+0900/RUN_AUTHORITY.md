# Clean extended adaptive rerun authority
Created: 2026-05-18T19:41:34+0900
Owner: leader-fixed only
Reason: prior outdir extended_adaptive_20260518T193519+0900 was contaminated by duplicate worker writers and is discarded.
Cohort: 79 rows where clean N=83 rerun had finish_reason=length and completion_tokens=max_tokens=512.
Policy: bounded ladder 1024,1536,2048,3072; stop per row at first non-length/non-cap-limited response; terminal length at 3072 remains unresolved_by_bound.

# evaluation

## Status
- This folder owns **scoring truth**, not final report prose.
- Canonical workflow/orchestration lives in `../../CODEX.md`.
- Numeric/report claims should trace back to machine-readable outputs generated through this lane or adjacent scripts.

## Key files
| File | Role |
|------|------|
| `compliance_scorer.py` | rule-level scoring helpers + compliance-rate computation |
| `evaluation.py` | response scoring + result aggregation |
| `judge.py` | judge prompt building and judge-response parsing |

## Working model
- Raw model responses become scored records first.
- Scored records become aggregates/summaries next.
- Only after that should reports/figures claim conclusions.

## Local rules
- If the machine-readable source artifact is missing, do not imply `PASS`; mark work `UNVERIFIED`.
- Behavioral/judge-driven paths must fail loudly enough to preserve traceability.
- If you change score schema or aggregation keys, update tests and any report script assumptions in the same task.
- Prefer explicit artifact paths over narrative descriptions when handing results to reviewers.

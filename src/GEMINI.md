# src/ Source Overview

## Status
- Canonical workflow/orchestration lives in `../CODEX.md`.
- This file is a **module-local map**, not the primary workflow contract.
- If this document conflicts with actual code or machine-readable artifacts, trust the code/artifacts first.

## Active modules
```text
src/
├── data_pipeline/   ← dataset download/preprocess + case-building helpers
├── compression/     ← Phase 2 / defense-method experiments
├── evaluation/      ← scoring, judge integration, aggregation helpers
├── models/          ← model request boundary
└── utils/           ← shared helpers (headers, formatting, plots)
```

Each subdirectory keeps its own `CLAUDE.md` / `GEMINI.md`. Keep paired files in sync.

## Current dependency shape
```text
data_pipeline ──→ evaluation ──→ utils
       │              │
       └──────→ models┘
compression ─────────→ evaluation/utils
scripts/* drive many end-to-end flows from project root
```

## Current truth sources
- Main case artifact in current experiment scripts is often `data/processed/experiment_cases_full.jsonl`.
- Some module docs or legacy routes may still mention `experiment_cases.jsonl`; verify the caller before changing schemas.
- Result artifacts usually live under `data/outputs/`.
- Report artifacts usually live under `docs/outputs/` and `docs/outputs/figures/`.

## Local rules
- When changing schemas, update downstream evaluation/report/test expectations in the same task.
- Do not claim numeric/report correctness without naming the machine-readable artifact path that proves it.
- Prefer minimal, factual docs here; orchestration policy belongs in `CODEX.md`.

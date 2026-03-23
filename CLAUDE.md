# 2026 LLM Evaluation Project

## Overview
Korean LLM reasoning evaluation pipeline. Collects model responses via OpenRouter API and scores them with quantitative metrics.

## Current Phase: Phase 1 — Core Pipeline
- Data loading/preprocessing (`src/data_pipeline/`)
- OpenRouter API calls + inference collection (`src/models/`)
- Auto-evaluation logic (`src/evaluation/`)
- Result visualization (`src/utils/`)

## Directory Structure
```
2026/
├── CLAUDE.md                  ← this file (load on session start)
├── .claude/rules/coding.md    ← coding rules (load on session start)
├── docs/                      ← reference docs (not auto-loaded)
│   ├── phase2-research-plan.md
│   └── architecture.md
├── configs/                   ← YAML experiment params
├── data/
│   ├── raw/                   ← original datasets (gitignored)
│   ├── processed/             ← preprocessed data
│   └── outputs/               ← LLM outputs + logs
├── notebooks/                 ← EDA + experiment notebooks
├── reports/figures/           ← evaluation visualizations
├── scripts/                   ← pipeline bash scripts
├── src/                       ← core source (has sub-CLAUDE.md)
└── tests/                     ← unit tests
```

## Key File Map
| Role | File |
|------|------|
| Data loading | `src/data_pipeline/load_datasets.py` |
| API calls | `src/models/open_router_request.py` |
| Evaluation | `src/evaluation/evaluation.py` |
| Visualization | `src/utils/visualize.py` |
| JSON utils | `src/utils/json_prettier.py` |

## Data Flow
```
data/raw/ → data_pipeline → data/processed/ → models → data/outputs/ → evaluation → reports/
```

## Next Steps
Phase 2-3 plan: see `docs/phase2-research-plan.md`.  
To load: *"Read docs/phase2-research-plan.md and design Phase 2"*
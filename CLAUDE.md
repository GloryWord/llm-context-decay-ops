# 2026 LLM Evaluation Project

## Git Rules
- After modifying all files, make sure to git add, commit, and push.

## Project Root
**Absolute path:** `/Users/kawai_tofu/Desktop/서울과학기술대학교_로컬/캡스톤디자인/capstone_dev/2026_eng`
All relative paths in this document are relative to this root. Always use this as the working directory.

## Compaction Rules
When compacting, always preserve the full list of modified files and any test commands

## Overview
Korean LLM reasoning evaluation pipeline. Collects model responses via OpenRouter API and scores them with quantitative metrics.

## Current Phase: Phase 1 v3 — 정밀 측정 재설계
- Phase 1 v1 (archived): Basic turn-count experiment with RuLES/IFEval
- Phase 1 v2 (archived): Project Aegis 312건, probe 다양성 결함 발견
- **Phase 1 v3 (active):** 변수 분리(A/B/C/D) + probe 다양화 + system_prompt_strategy 추가
  - A: 컨텍스트 길이 vs 턴 수 분리
  - B: 규칙 수 인지 부하 측정
  - C: 적대적 대화 가속 효과
  - D: System Prompt 반복 주입 효과
- Phase 2 (보류): Context compression — Phase 1 완료 후 결정

## Directory Structure
```
2026_eng/
├── CLAUDE.md                  ← this file (load on session start)
├── .claude/rules/coding.md    ← coding rules (load on session start)
├── docs/                      ← reference docs (not auto-loaded)
│   ├── phase1-research-plan.md
│   ├── phase2-research-plan.md
│   └── token-save-guide.md
├── configs/                   ← YAML experiment params
│   ├── preprocess.yaml        ← Phase 1 preprocessing config
│   └── compression.yaml       ← Phase 2 compression config
├── data/
│   ├── raw/                   ← original datasets (gitignored)
│   ├── processed/             ← preprocessed data + compressed cases
│   └── outputs/               ← LLM outputs + logs
├── reports/figures/           ← evaluation visualizations
├── src/
│   ├── data_pipeline/         ← Phase 1: download, preprocess, case generation
│   ├── compression/           ← Phase 2: compression methods
│   ├── models/                ← OpenRouter API inference
│   ├── evaluation/            ← compliance scoring
│   └── utils/                 ← visualization, JSON utils
└── tests/                     ← unit tests
```

## Key File Map
| Role | File |
|------|------|
| Pipeline entry point | `src/data_pipeline/load_datasets.py` |
| Dataset download | `src/data_pipeline/download_datasets.py` |
| Token utilities | `src/data_pipeline/token_utils.py` |
| RuLES preprocessing | `src/data_pipeline/preprocess_rules.py` |
| IFEval preprocessing | `src/data_pipeline/preprocess_ifeval.py` |
| ShareGPT preprocessing | `src/data_pipeline/preprocess_sharegpt.py` |
| MultiChallenge preprocessing | `src/data_pipeline/preprocess_multichallenge.py` |
| Project Aegis probes & scoring | `src/data_pipeline/generate_multi_rule_probes.py` |
| Experiment case generation | `src/data_pipeline/generate_experiment_cases.py` |
| Phase 1 config | `configs/preprocess.yaml` |
| Compression base class | `src/compression/base.py` |
| Sliding window compressor | `src/compression/sliding_window.py` |
| Selective context compressor | `src/compression/selective_context.py` |
| Turn summarization compressor | `src/compression/summarize_turns.py` |
| Prompt reinforcement | `src/compression/system_prompt_reinforce.py` |
| Compression orchestrator | `src/compression/apply_compression.py` |
| Phase 2 config | `configs/compression.yaml` |
| API calls | `src/models/open_router_request.py` |
| Evaluation | `src/evaluation/evaluation.py` |
| Visualization | `src/utils/visualize.py` |

## Data Flow
```
Phase 1 v2:
  download_datasets.py → preprocess_*.py → generate_multi_rule_probes.py → generate_experiment_cases.py
      → data/processed/experiment_cases.jsonl (312+ cases, Project Aegis)

Phase 2:
  apply_compression.py → data/processed/compressed_cases/{variant}/experiment_cases.jsonl
      ↓
  open_router_request.py → data/outputs/{model}/{variant}/results.jsonl
      ↓
  evaluation.py → reports/evaluation_summary.json + reports/scored_results.jsonl
      ↓
  visualize.py → reports/figures/{compliance_curves,compression_vs_compliance,defense_effectiveness}.png
```

## Next Steps
Phase 3 plan: see `docs/phase1-research-plan.md` line 93 (hybrid compression strategy).
Dev history: `.claude/dev_history/` 이곳에 작업한 내용을 md 파일로 남기세요. 기존에 있는 md 파일의 이름과 형식, 내용 등을 예시로 참고하세요.
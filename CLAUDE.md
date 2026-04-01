# LLM Context Decay 실험 프로젝트

## Git Rules
- After modifying all files, make sure to git add, commit, and push.

## Project Root
**Absolute path:** `/Users/kawai_tofu/Desktop/01_학업_서울과기대/서울과학기술대학교_로컬/캡스톤디자인/capstone_dev/Multi-Agent-Workflow/llm-context-decay-ops`
All relative paths in this document are relative to this root.

## Compaction Rules
When compacting, always preserve the full list of modified files and any test commands

## Overview
System Prompt Compliance Threshold Detection in LLMs.
Multi-turn 대화에서 시스템 프롬프트 규칙 준수율의 붕괴 임계점을 탐지하는 실험 파이프라인.

## Research Questions (Q4 제외)
| ID | 질문 | 핵심 변수 |
|----|------|----------|
| Q1 | 복수 규칙의 동시 준수율이 대화 턴 수 증가에 따라 어떻게 변하는가? | rule_count × turn_count |
| Q2 | 규칙 유형(형식, 언어, 행동, 페르소나)에 따라 붕괴 순서에 차이가 있는가? | rule_category |
| Q3 | 무해 대화 vs 점진적 에스컬레이션 공격 조건에서 붕괴 시점과 속도가 달라지는가? | attack_intensity |

## Experiment Variables
| 변수 | 수준 |
|------|------|
| rule_count | 1, 3, 5, 7 |
| turn_count | 1, 5, 10, 15 |
| attack_intensity | benign, adversarial (Crescendo-style) |
| 모델 | Llama 3.1 8B (local vLLM), DeepSeek R1 (OpenRouter API) |
| 반복 | 5회/셀 |

## Directory Structure
```
llm-context-decay-ops/
├── CLAUDE.md                  ← this file
├── .claude/rules/coding.md    ← coding rules
├── docs/
│   ├── [Capstone]_이종웅_Lit_Review_and_Exp_Design_22110157.md  ← 연구계획서
│   ├── experimental_design.md                                    ← 상세 실험 설계
│   ├── outputs/                                                  ← 산출물 (보고서 등)
│   ├── hcom/                                                     ← hcom/acpx 인프라 문서
│   ├── multi-agent-working-history/                              ← 에이전트 작업 기록
│   └── imgs/                                                     ← 참조 이미지
├── data/
│   ├── raw/                   ← original datasets (gitignored)
│   ├── processed/             ← preprocessed data
│   └── outputs/               ← LLM outputs + logs
├── scripts/
│   ├── README.md          ← 오케스트레이터 전환 가이드
│   ├── claude_only/       ← Claude Code 오케스트레이터 전용 (eval_all.sh 등)
│   └── gemini_only/       ← Gemini 오케스트레이터 전용 (현재 사용 중 아닐 시 상황 상이할 수 있음)
├── src/
│   ├── data_pipeline/         ← download, preprocess, case generation
│   ├── compression/           ← Phase 2용 (보류 중)
│   ├── models/                ← OpenRouter API inference
│   ├── evaluation/            ← compliance scoring + LLM-judge
│   └── utils/                 ← visualization, JSON utils
└── tests/                     ← unit tests
```

## Key File Map
| Role | File |
|------|------|
| 연구계획서 | `docs/[Capstone]_이종웅_Lit_Review_and_Exp_Design_22110157.md` |
| 상세 실험 설계 | `docs/experimental_design.md` |
| 벤치마크 매핑 보고서 | `docs/outputs/benchmark_reuse_mapping.md` |
| Pipeline entry point | `src/data_pipeline/load_datasets.py` |
| Dataset download | `src/data_pipeline/download_datasets.py` |
| Token utilities | `src/data_pipeline/token_utils.py` |
| RuLES preprocessing | `src/data_pipeline/preprocess_rules.py` |
| IFEval preprocessing | `src/data_pipeline/preprocess_ifeval.py` |
| ShareGPT preprocessing | `src/data_pipeline/preprocess_sharegpt.py` |
| MultiChallenge preprocessing | `src/data_pipeline/preprocess_multichallenge.py` |
| Experiment case generation | `src/data_pipeline/generate_experiment_cases.py` |
| Compliance scorer | `src/evaluation/compliance_scorer.py` |
| Evaluation (IFEval) | `src/evaluation/evaluation.py` |
| LLM Judge | `src/evaluation/judge.py` |
| API calls | `src/models/open_router_request.py` |
| Visualization | `src/utils/visualize.py` |
| Cursor 평가 (Claude Code용) | `scripts/claude_only/eval_cursor.sh` |
| Gemini 평가 (Claude Code용) | `scripts/claude_only/eval_cycle.sh` |
| 통합 평가 — Claude Code 오케스트레이터 | `scripts/claude_only/eval_all.sh` |
| 오케스트레이터 전환 가이드 | `scripts/README.md` |
| 308 케이스 생성기 | `scripts/generate_full_cases.py` |
| 메인 실험 러너 | `scripts/run_experiment.py` |
| 생성된 실험 케이스 | `data/processed/experiment_cases_full.jsonl` |

## Data Flow
```
Phase 1:
  download_datasets.py → preprocess_*.py → generate_experiment_cases.py
      → data/processed/sample_cases_v4.jsonl (현재 10개 샘플)
      ↓
  open_router_request.py → data/outputs/{model}/results.jsonl
      ↓
  compliance_scorer.py + judge.py → scored_results.jsonl
      ↓
  visualize.py → figures/
```

## Scoring Methods
| 규칙 유형 | 채점 방법 | 자동화 수준 |
|----------|----------|-----------|
| 형식 (글자 수, 접두어) | regex / char count | 100% 자동 |
| 언어 (한국어 전용) | langdetect | 100% 자동 |
| 행동 (주제 거부) | LLM-judge (DeepSeek V3) | 반자동 |
| 페르소나 (존댓말) | 한국어 어미 패턴 매칭 | 90% 자동 |

## Multi-Agent Workflow (필수 준수)
- **실행자**: Claude Code (이 세션)
- **평가자 1**: Gemini CLI (acpx headless) — 완결성/학문적 엄밀성 평가
- **평가자 2**: Cursor Agent — 모델별 역할 분담:
  - `composer-2`: 코드 구조/아키텍처 검토, 파이프라인 일관성, 리팩토링 제안 (기본 평가)
  - `gpt-5.4-high`: 논리 정합성 검토, 계획 수립 시 연구 설계 검증 (일반 문서)
  - `gpt-5.4-xhigh`: 최종 검증 — 논문 수준 엄밀성, 수치-표-그래프 정합성 (고비용, `--final`로만 실행)
  - 문서가 길면(코드+로그 포함) `1M` 계열 자동 선택 (gpt-5.4-high → gpt-5.4-1m-high 등)
- **통합 평가**: `scripts/claude_only/eval_all.sh` — Gemini + Cursor 병렬 실행
- **개별 평가**: `scripts/claude_only/eval_cycle.sh` (Gemini) / `scripts/claude_only/eval_cursor.sh` (Cursor)
- **Context 관리**:
  - Gemini: 15회 평가마다 세션 자동 리셋
  - Cursor: `agent -p` (print mode)는 매 호출 독립 세션. 대화형 사용 시 `/compact` (압축), `/clear` (초기화)
- **인프라 문서**: `docs/hcom/acpx-integration-analysis.md`, `docs/hcom/acpx-reconnect-issue.md`
- **오케스트레이터 전환 가이드**: `scripts/README.md`

### 절대 규칙: 평가 없이 다음 작업 금지
1. **매 작업 완료 후** 자동으로 `bash scripts/claude_only/eval_all.sh <산출물경로>` 실행 — 사용자가 지시하지 않아도 반드시 실행
2. **기본값**: Gemini + Cursor (Composer2 + Codex) 교차 검증
3. **평가 완료 후** 사용자에게 "Codex High 최종 검증을 실행할까요?" 반드시 질문. 사용자가 승인하면 `--final` 실행
4. **최소 1개 평가자의 결과를 수신한 후에만** 다음 작업으로 진행
4. **평가 실패 시**: 사용자에게 즉시 보고하고 작업 중단. 절대 무시하고 진행하지 말 것
5. **작업 기록** 반드시 `docs/multi-agent-working-history/` 에 남길 것
6. 기록 형식: `YYYY-MM-DD_HHMM_키워드.md`
7. 기록 내용: 작업 내용 + 평가 결과 (Gemini/Cursor) + 조치 사항
8. `.claude/hooks/eval_gate.sh` 가 미평가 산출물 경고를 출력함

**이 규칙을 위반하면 사용자의 시간과 비용을 낭비하는 것이다. 절대 생략하지 마라.**

## Dev History
Work logs: `docs/multi-agent-working-history/` (날짜_시간_키워드.md)

## Completion Report Pattern
```
## {Task Name} Summary

### Work Performed
- bullet list

### Key Findings
| table of quantitative results |

### Remaining Issues (IMPORTANT)
- unresolved problems MUST be surfaced
```

Rules:
- Lead with results, not process
- Always include quantitative evidence
- **Remaining Issues is the most important section**
- Keep it concise: prefer tables over paragraphs

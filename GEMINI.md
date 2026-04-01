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
├── GEMINI.md                  ← this file (Gemini 오케스트레이터 규칙)
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
├── scripts/                   ← 자동화 스크립트 (eval_cycle.sh 등)
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
| Cursor 평가 (Gemini 오케스트레이터용) | `scripts/gemini_only/eval_cursor.sh` |
| 통합 평가 진입점 | `scripts/gemini_only/eval_all.sh` |
| 평가 사이클 래퍼 | `scripts/gemini_only/eval_cycle.sh` |
| 비상 리셋 | `scripts/gemini_only/eval_reset_session.sh` |
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

> **[구조 변경]** 과거 Claude/Cursor 기반에서 새로운 ACPX(AI 상호 평가 Agents) 기반 체계로 개편되었습니다.
> 기존: Claude Code(오케스트레이터) → Gemini(평가자1) + Cursor(평가자2)
> **현재: Gemini(오케스트레이터) → MJ_Codex(수정/감사) → Cursor AI(최종 검증)**

- **1. 오케스트레이터 (Gemini, 이 인스턴스)**: 교수 피드백을 `packet.yaml` 형식으로 정리, 라운팅(general vs numeric) 제어
- **2. 수정자 (Reviser, MJ_Codex / gpt-5.4)**: `packet.yaml`을 받아 실제 산출물(`revised.md`)을 생성
- **3. 수치 감사자 (Numeric Auditor, MJ_Codex / gpt-5.3-codex)**: 숫자/표 관련 수정 시 정합성을 감사 (`numeric_audit.yaml` 생성)
- **4. 최종 검증자 (Final Verifier, Cursor / gpt-5.4-high)**: 최종 산출물을 받아 패스(PASS)/반려(BLOCK) 판정 (`verdict.yaml` 생성)

- **평가 스크립트 경로**: `scripts/gemini_only/` (Gemini 오케스트레이터 전용)
  - 루프 파이프라인(작업 후 평가 시 실행): `bash scripts/gemini_only/eval_all.sh <PACKET_YAML> <TARGET_MD> [KEYWORD]`
  - 결과물 저장 경로: `docs/multi-agent-working-history/YYYY-MM-DD/HHMMSS_KEYWORD/`
- **⚠️ 금지 규칙**: 
  - `composer-2`는 완전히 제거하였으므로 절대 평가 과정에 사용 금지.
  - 범용 리뷰어를 2명 이상 병렬로 배치 금지.
  - 이미 패스(PASS)인 부분에 추가 리뷰 금지.
- **Context 관리**:
  - `MJ_Codex`와 `Cursor` 호출 시 가능한 One-shot으로 관리 (`max_loops = 2` 정책 적용)
- **인프라 문서**: `docs/hcom/acpx-integration-analysis.md`, `docs/acpx_prompts/ACPX_OPERATING_SPEC.md`

### 절대 규칙: 평가 없이 다음 작업 금지
1. **수정 작업 후** 사용자가 제공한 피드백이 있다면 반드시 ACPX 검증 루프(`eval_all.sh`)를 가동할 것.
2. 루프 컨트롤 속성(Max Loops)은 최대 2회. 두 번 연속 검증 실패(BLOCK) 시 사용자에게 수동 검토를 요청.
3. **최종 검증자(Cursor)의 판정 결과를 수신한 후에만** 다음 작업으로 진행.
4. **검증 실패(BLOCK) 시**: 무시하고 진행하지 말고, `Reviser`에게 지적사항을 다시 넘겨주어 재수정 루프 실행.
5. **작업 기록** 반드시 `docs/multi-agent-working-history/` 에 남길 것
6. 기록 형식: `YYYY-MM-DD/HHMMSS_KEYWORD/` 폴더 내에 저장
7. 기록 내용: 패킷 생성 내용 + 각 Agent 수행 결과(`verdict.yaml` 판정 등) + 조치 사항

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

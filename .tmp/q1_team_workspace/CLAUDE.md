# LLM Context Decay 실험 프로젝트

## Git Rules
- After modifying all files, make sure to git add, commit, and push.

## Project Root
**Absolute path:** `/Users/kawai_tofu/Desktop/01_학업_서울과기대/서울과학기술대학교_로컬/캡스톤디자인/capstone_dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops`
All relative paths in this document are relative to this root.

## Compaction Rules
When compacting, always preserve the full list of modified files and any test commands.

## Workflow Status (Important)
- **현재 canonical workflow 문서:** `CODEX.md`
- 이 파일은 **Claude Code / `scripts/claude_only/` 브리지용 레거시 참고 문서**다.
- 이 저장소의 기본 오케스트레이터는 더 이상 Claude 전용 구성이 아니라 **Codex + OMX**다.
- 사용자는 기본적으로 **초기 요구사항 입력**과 **최종 blocker 검토**만 담당한다.
- 따라서 이 파일의 예전 “매 작업마다 외부 평가 강제” 규칙은 더 이상 기본값이 아니다.

## Overview
System Prompt Compliance Threshold Detection in LLMs.
Multi-turn 대화에서 시스템 프롬프트 규칙 준수율의 붕괴 임계점을 탐지하는 실험 파이프라인.

## Research Questions (Q4 기본 제외)
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

## Key Working Areas
- `src/data_pipeline/` — 데이터 수집/전처리/케이스 생성
- `src/evaluation/` — compliance scoring / judge / evaluation
- `src/compression/` — Phase 2 후보군
- `src/models/` — 모델 호출 경계
- `scripts/run_experiment.py`, `scripts/run_experiment_fast.py` — 실험 실행
- `scripts/generate_full_cases.py`, `scripts/generate_report.py` — 케이스/리포트 생성
- `data/processed/`, `data/outputs/` — machine-readable artifact
- `docs/outputs/` — 보고서/figure 산출물
- `docs/multi-agent-working-history/` — 작업 기록

## Drift Warning
이 저장소에는 historical drift가 있다. 아래는 항상 실제 파일 기준으로 재확인한다.
- `CODEX.md`, `CLAUDE.md`, `GEMINI.md`, `scripts/README.md`의 workflow 설명은 완전히 같지 않을 수 있다.
- `docs/acpx_prompts/*`는 **교수 피드백 문서 수정 루프** 기준이다.
- `docs/experimental_design.md` 같은 일부 경로는 legacy reference일 수 있다.
- `experiment_cases.jsonl` vs `experiment_cases_full.jsonl` naming drift가 있었다.
- 보고서 reviewer가 참조하는 summary JSON / figure가 git에 없을 수 있다.

## Claude-only Bridge Workflow (Legacy / Opt-in)
이 섹션은 **Claude Code를 별도 오케스트레이터로 다시 쓸 때만** 참고한다.
기본값은 아니다.

### 언제만 쓰는가
- Codex/OMX가 이미 로컬에서 작업과 검증을 끝냈고
- 추가적인 외부 교차 리뷰가 필요하며
- 산출물이 단일 파일 또는 좁은 evidence pack으로 정리되어 있을 때

### 기본 흐름
1. **Codex/OMX**가 먼저 계획/수정/로컬 검증을 수행한다.
2. 외부 시각이 필요할 때만 `scripts/claude_only/`를 사용한다.
3. Claude-only 결과는 **보조 리뷰**로 취급한다.
4. 동일 blocker가 반복되거나 reviewer 둘 다 실패하면 사용자에게 최종 blocker만 전달한다.

### 사용 가능한 스크립트
```bash
# finished deliverable에 대한 보조 교차 리뷰
bash scripts/claude_only/eval_all.sh <deliverable_path>

# 개별 Gemini 리뷰
bash scripts/claude_only/eval_cycle.sh <deliverable_path>

# 개별 Cursor 리뷰
bash scripts/claude_only/eval_cursor.sh <deliverable_path>
```

### 운영 규칙
- `scripts/claude_only/*`는 **매 작업마다 자동 실행하지 않는다.**
- 로컬 evidence pack 없이 외부 reviewer에게 바로 넘기지 않는다.
- 외부 reviewer의 prose는 참고 의견이지, 단독 PASS/BLOCK gate가 아니다.
- 최종 사용자 보고는 **초기 요구사항 재진술 + blocker/remaining risk** 중심으로 짧게 한다.

## External Review Packet Rule
Claude-only bridge를 쓸 때는 아래만 넘긴다.
- 목표 산출물 경로
- 변경 파일 목록
- 실행한 검증 명령
- 핵심 결과/숫자 출처
- reviewer에게 물을 질문 1~3개

아래는 넘기지 않는다.
- 이전 리뷰어 장문 prose 전체
- repo 전체 dump
- 이미 기각된 blocker 반복 전달

## Completion Report Pattern
```
## {Task Name} Summary

### Work Performed
- bullet list

### Evidence
- files changed
- commands run
- key outputs

### Remaining Issues (IMPORTANT)
- unresolved blockers / risks only
```

Rules:
- Lead with results, not process.
- Prefer evidence over opinions.
- **Remaining Issues** is still the most important section.
- If verification is incomplete, say `UNVERIFIED` explicitly.

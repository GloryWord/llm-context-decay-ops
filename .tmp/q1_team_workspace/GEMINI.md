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
- 이 파일은 **Gemini / ACPX 문서 수정 루프용 레거시 참고 문서**다.
- 기본 오케스트레이션은 더 이상 Gemini 중심이 아니라 **Codex + OMX 중심**이다.
- 이 파일의 역할은 repo 전체 orchestration이 아니라, **교수 피드백 기반 문서 수정** 같은 좁은 route를 설명하는 것이다.
- 사용자는 기본적으로 **초기 packet 요구사항 확인**과 **최종 BLOCK 검토**만 하면 된다.

## Overview
System Prompt Compliance Threshold Detection in LLMs.
Multi-turn 대화에서 시스템 프롬프트 규칙 준수율의 붕괴 임계점을 탐지하는 실험 파이프라인.

## Research Questions (Q4 기본 제외)
| ID | 질문 | 핵심 변수 |
|----|------|----------|
| Q1 | 복수 규칙의 동시 준수율이 대화 턴 수 증가에 따라 어떻게 변하는가? | rule_count × turn_count |
| Q2 | 규칙 유형(형식, 언어, 행동, 페르소나)에 따라 붕괴 순서에 차이가 있는가? | rule_category |
| Q3 | 무해 대화 vs 점진적 에스컬레이션 공격 조건에서 붕괴 시점과 속도가 달라지는가? | attack_intensity |

## Key Working Areas
- `docs/acpx_prompts/` — ACPX role prompts (legacy doc-revision route)
- `scripts/gemini_only/eval_all.sh` — packet 기반 문서 수정 루프 진입점
- `scripts/gemini_only/acpx_mj_runner.sh` — MJ_Codex 호출 래퍼
- `scripts/gemini_only/acpx_cursor_runner.sh` — Cursor verifier 호출 래퍼
- `docs/multi-agent-working-history/` — loop 결과 저장

## Gemini-only ACPX Route (Legacy / Opt-in)
이 route는 **문서 수정 작업**, 특히 교수 피드백 반영처럼 packet 기반 문서 revise가 필요할 때만 쓴다.

### 적합한 작업
- `docs/outputs/*.md`, 보고서 초안, 발표용 설명문 수정
- numeric / method sensitive 문단 수정
- professor feedback을 change ledger로 정리해 재작성해야 하는 경우

### 부적합한 작업
- `src/`, `scripts/`, `tests/` 코드 수정
- 실험 실행/재시작/체크포인트 관리
- repo 전체 primary orchestrator 역할
- evidence 없는 숫자 검증

### 기본 흐름
1. **Codex/OMX**가 먼저 로컬 사실관계와 evidence pack을 확보한다.
2. 필요 시 feedback을 `packet.yaml`로 좁게 정리한다.
3. 아래 루프를 실행한다.
   ```bash
   bash scripts/gemini_only/eval_all.sh <packet.yaml> <target.md> [keyword]
   ```
4. MJ_Codex reviser / numeric auditor / Cursor final verifier가 최대 2회 루프를 돈다.
5. `PASS`면 문서 반영, `BLOCK`이 2회 반복되면 human escalation.

### 핵심 규칙
- `composer-2`는 이 Gemini-only route에 넣지 않는다.
- generic reviewer를 2명 이상 병렬 배치하지 않는다.
- 이전 리뷰 prose를 다음 에이전트에 길게 넘기지 않는다.
- local evidence 없이 packet만 만들어 reviewer를 돌리지 않는다.
- 최종 사용자 보고는 **packet 요약 + 최종 BLOCK만** 전달한다.

## Packet Contract
필수 포함 항목:
- `document_path`
- `current_document`
- `prof_feedback`
- `change_ledger`
- `previous_blockers` (있을 때만)

가능하면 추가할 것:
- 숫자/표 출처 파일
- 관련 figure 경로
- machine-readable summary 경로

포함하지 말 것:
- 이전 리뷰어 장문 prose 전체
- repo 전체 dump
- unrelated code/log

## Completion Report Pattern
```
## {Task Name} Summary

### Work Performed
- bullet list

### Evidence
- packet path
- target path
- verifier verdict path

### Remaining Issues (IMPORTANT)
- unresolved blockers / risks only
```

Rules:
- PASS/BLOCK을 짧고 명확하게 다룬다.
- loop가 끝나면 장문 감상 대신 blocker만 남긴다.
- verification이 부족하면 `UNVERIFIED`로 표시한다.

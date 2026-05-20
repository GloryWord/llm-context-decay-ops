# ACPX Team Spec for Professor-Feedback Revisions

## Purpose

이 정의서는 "교수님 피드백을 반영해 기존 연구 문서를 수정하는 작업"에 맞춘 ACPX 운영 규칙이다.
핵심 목적은 다음 세 가지다.

- 리뷰 루프를 줄이고 실제 수정 산출물을 강제한다.
- 숫자, 표, threshold, method 변경이 있을 때만 추가 감사를 붙인다.
- 같은 blocker가 반복될 때 자동으로 멈추고 사람 판단으로 넘긴다.

## What To Keep From the Claude Proposal

- "수정 실행자"를 별도 역할로 둔다.
- 검증자는 한 명만 둔다.
- 반려가 나오면 검증자 의견을 수정자에게 되돌려 재수정한다.
- 루프 횟수는 최대 2회로 제한한다.
- 수정자 출력은 반드시 실행 가능한 수정 산출물이어야 한다.

## What To Discard Or Tighten

- 문서 수정 루프에 `composer2`는 넣지 않는다.
- 범용 리뷰어를 2명 이상 병렬로 붙이지 않는다.
- 이전 에이전트의 장문 평가문을 다음 에이전트에 그대로 넘기지 않는다.
- 수정자에게 "평가"를 시키지 않는다. 수정자 임무는 오직 수정이다.
- 검증자는 새로운 아이디어를 확장하지 않는다. `PASS` 또는 `BLOCK`만 낸다.
- "수정 후 승인 가능" 같은 조건부 승인 문구는 금지한다. 현재 상태 기준으로만 판정한다.

## Default Topology

### Route A: General professor-feedback revision

1. Orchestrator
2. Reviser
3. Final Verifier

### Route B: Numeric or method-sensitive revision

1. Orchestrator
2. Reviser
3. Numeric Auditor
4. Final Verifier

## Runtime Naming

이 문서에서는 런타임을 모델명 앞에 붙여 구분한다.

- `Gemini/...`는 메인 오케스트레이터에서 실행된다.
- `MJ/...`는 `MJ_Codex`에서 실행된다.
- `Cursor/...`는 `Cursor AI` 내부에서 실행된다.

## Fixed Runtime Policy

- `composer2`는 완전히 제거한다.
- 메인 `Orchestrator`는 항상 `Gemini`다.
- `Reviser`, `Numeric Auditor`는 `MJ_Codex`에서 실행한다.
- `Final Verifier`는 `Cursor AI`에서만 실행한다.
- `Final Verifier`는 `Cursor/gpt-5.4-high` 또는 `Cursor/gpt-5.4-extra-high`만 허용한다.

## Recommended Model Mapping

- `Orchestrator`: `Gemini/Auto Routing` 기본, 복잡한 피드백은 `Gemini/gemini-3.1-pro-preview`로 고정
- `Reviser`: `MJ/gpt-5.4` 기본, 대형 수정은 `MJ/gpt-5.2`
- `Numeric Auditor`: `MJ/gpt-5.3-codex` 기본, 더 깊은 수치 감사는 `MJ/gpt-5.1-codex-max`
- `Final Verifier`: `Cursor/gpt-5.4-high` 기본, 제출 직전은 `Cursor/gpt-5.4-extra-high`

핵심은 모델 수가 아니라 역할 분리다. 일반 문서 수정에 범용 리뷰어를 여러 명 붙이면 느려지고 같은 지적만 재생산된다.

## Standard Input Packet

모든 역할은 아래 입력만 받는다.

- `document_path`
- `current_document`
- `prof_feedback`
- `change_ledger`
- `previous_blockers` if any

다음 입력은 전달하지 않는다.

- 이전 에이전트의 장문 감상문
- 스타일 제안만 잔뜩 담긴 polishing 메모
- 이미 기각된 blocker 목록

## Change Ledger Contract

`change_ledger`는 최대 3~7개 항목만 유지한다.

각 항목 필수 필드:

- `id`
- `section`
- `issue`
- `required_change`
- `evidence`
- `allowed_scope`
- `numeric_sensitive`
- `status`

템플릿은 [CHANGE_LEDGER_TEMPLATE.yaml](/mnt/acpx_prompts/CHANGE_LEDGER_TEMPLATE.yaml)에 있다.

## Output Contract By Role

### Orchestrator

- 출력은 `route decision + change ledger + run budget`만 허용
- 문서 본문 수정 금지
- 장문 리뷰 금지

### Reviser

- 출력은 반드시 실제 수정 산출물이어야 함
- 허용 출력:
  - direct file edit
  - unified diff
  - section replacement blocks
- 금지 출력:
  - 평가문만 출력
  - "어떻게 고치면 좋다" 수준의 조언만 출력
  - 승인/반려 판정

### Numeric Auditor

- 숫자, 표, 산식, method-to-claim 정합성만 본다
- 최대 blocker 5개
- 문체와 구조 평가는 금지

### Final Verifier

- `PASS` 또는 `BLOCK`만 출력
- `BLOCK`일 때만 최대 5개 지적
- 새로운 연구 아이디어 추가 금지
- 동일 blocker가 2회 반복되면 `ESCALATE_TO_HUMAN: true`

## Stop Rules

- `max_loops = 2`
- 같은 blocker가 의미 있게 줄지 않으면 즉시 중단
- `numeric_sensitive = false`인 작업에는 Numeric Auditor를 붙이지 않음
- Final Verifier가 `PASS`를 내면 추가 리뷰 금지

## Failure Modes This Spec Prevents

- 문서를 코드처럼 읽고 역할이 빗나가는 문제
- step2가 이미 찾은 문제를 step3가 다시 길게 반복하는 문제
- 수정자 없이 평가자만 있는 구조
- 반려 사유가 문서 수정 instruction이 아니라 감상문으로 전달되는 문제
- 동일 문서에 대해 다중 범용 리뷰어가 서로 비슷한 blocker를 재생산하는 문제

## Practical Policy

- 문서 수정은 `single writer + narrow verifier` 원칙으로 운영한다.
- 표, threshold, formula, aggregation, judge setting이 바뀌면 Numeric Auditor를 켠다.
- 표면 문체 polishing은 마지막 5분에만 허용한다.
- 교수님 피드백 반영 작업은 속도보다 정합성이 우선이지만, 리뷰 수를 늘려 정합성을 얻지 않는다.
- 메인 orchestration은 `Gemini`에서 수행한다.
- 초안 작성과 수치 감사는 `MJ_Codex`에서 끝낸다.
- 마지막 승인만 `Cursor AI High/Extra High`에 맡긴다.

## File Set

- [ORCHESTRATOR_PROMPT.md](/mnt/acpx_prompts/ORCHESTRATOR_PROMPT.md)
- [REVISER_PROMPT.md](/mnt/acpx_prompts/REVISER_PROMPT.md)
- [NUMERIC_AUDITOR_PROMPT.md](/mnt/acpx_prompts/NUMERIC_AUDITOR_PROMPT.md)
- [FINAL_VERIFIER_PROMPT.md](/mnt/acpx_prompts/FINAL_VERIFIER_PROMPT.md)
- [CHANGE_LEDGER_TEMPLATE.yaml](/mnt/acpx_prompts/CHANGE_LEDGER_TEMPLATE.yaml)
- [ACPX_EXECUTION_TEMPLATES.md](/mnt/acpx_prompts/ACPX_EXECUTION_TEMPLATES.md)
- [ACPX_MODEL_POLICY.md](/mnt/acpx_prompts/ACPX_MODEL_POLICY.md)
- [ACPX_ONE_PAGE_PROMPT_PACK.md](/mnt/acpx_prompts/ACPX_ONE_PAGE_PROMPT_PACK.md)

# ACPX Model Policy

## Core Policy

- `composer-2`는 완전히 제거한다.
- 메인 `Orchestrator`는 항상 `Gemini`다.
- `Cursor AI`는 `Final Verifier` 전용이다.
- `Reviser`, `Numeric Auditor`는 `MJ_Codex`에서 실행한다.
- `Final Verifier`는 `Cursor/gpt-5.4-high` 또는 `Cursor/gpt-5.4-extra-high`만 허용한다.
- 범용 리뷰어 2명 이상 병렬 배치는 금지한다.

## Runtime Notation

- `Gemini/...` = 메인 오케스트레이터
- `MJ/...` = `MJ_Codex`에서 실행되는 모델
- `Cursor/...` = `Cursor AI` 내부에서 실행되는 모델

## Gemini Orchestrator Roles

- `Gemini/Auto Routing`: 기본 packetize, route, loop control
- `Gemini/gemini-3.1-pro-preview`: 긴 교수 피드백과 충돌 정리
- `Gemini/gemini-3-flash-preview`: 짧은 피드백과 빠른 ledger 생성

## MJ_Codex Model Roles

- `MJ/gpt-5.4`: 기본 수정자
- `MJ/gpt-5.4-mini`: 소규모 수정 또는 가벼운 blocker 정리
- `MJ/gpt-5.3-codex`: 수치/방법/정합성 감사 기본값
- `MJ/gpt-5.3-codex-spark`: 가장 빠른 pre-check/triage
- `MJ/gpt-5.2-codex`: 중간급 기술 감사 대안
- `MJ/gpt-5.2`: 긴 문서와 장시간 수정 작업용
- `MJ/gpt-5.1-codex-max`: 깊은 수치 추론 감사
- `MJ/gpt-5.1-codex-mini`: 초경량 분류/패킷 점검 전용

## Allowed Model Map

### Default

- `Orchestrator`: `Gemini/Auto Routing`
- `Reviser`: `MJ/gpt-5.4`
- `Numeric Auditor`: `MJ/gpt-5.3-codex`
- `Final Verifier`: `Cursor/gpt-5.4-high`

### If Feedback Is Messy But Still Text-Only

- `Orchestrator`: `Gemini/gemini-3.1-pro-preview`
- `Reviser`: `MJ/gpt-5.4`
- `Final Verifier`: `Cursor/gpt-5.4-high`

단, 이 경우도 `Orchestrator`만 강화한다. 범용 리뷰어를 추가하지 않는다.

### If The Rewrite Is Large

- `Orchestrator`: `Gemini/gemini-3.1-pro-preview`
- `Reviser`: `MJ/gpt-5.2`
- `Numeric Auditor`: `MJ/gpt-5.2-codex` or `MJ/gpt-5.3-codex`
- `Final Verifier`: `Cursor/gpt-5.4-high`

### If Numeric Logic Is Hairy

- `Orchestrator`: `Gemini/Auto Routing`
- `Reviser`: `MJ/gpt-5.4`
- `Numeric Auditor`: `MJ/gpt-5.1-codex-max`
- `Final Verifier`: `Cursor/gpt-5.4-high`

### If Submission-Final

- `Orchestrator`: `Gemini/gemini-3.1-pro-preview`
- `Reviser`: `MJ/gpt-5.4`
- `Numeric Auditor`: `MJ/gpt-5.3-codex` if needed
- `Final Verifier`: `Cursor/gpt-5.4-extra-high`

## Disallowed Assignments

- `composer-2` anywhere in the markdown report revision loop
- `MJ_Codex` as main orchestrator
- `Cursor AI` as draft writer or numeric auditor
- `MJ/gpt-5.1-codex-mini` as main reviser
- `MJ/gpt-5.3-codex-spark` as final verifier-equivalent
- `Cursor/gpt-5.4-high` as both reviser and verifier in the same loop

마지막 금지 규칙은 "자기수정 자기검증" 편향을 줄이기 위한 것이다.

## Presets

### Preset A: Fast And Safe

```text
Gemini/Auto Routing packetizer
-> MJ/gpt-5.4 reviser
-> Cursor/gpt-5.4-high verifier
```

권장 대상:

- 일반적인 교수님 피드백 반영
- 문장, 구조, 주장 수위, limitation, framing 수정

### Preset B: Numeric Safe

```text
Gemini/Auto Routing packetizer
-> MJ/gpt-5.4 reviser
-> MJ/gpt-5.3-codex numeric auditor
-> Cursor/gpt-5.4-high verifier
```

권장 대상:

- 표/수치/threshold/method 관련 수정

### Preset C: Large Rewrite

```text
Gemini/gemini-3.1-pro-preview packetizer
-> MJ/gpt-5.2 reviser
-> MJ/gpt-5.2-codex or MJ/gpt-5.3-codex auditor if needed
-> Cursor/gpt-5.4-high verifier
```

권장 대상:

- 장문 섹션 재구성
- 여러 절을 함께 다시 엮어야 하는 수정

### Preset D: Submission-Final

```text
Gemini/gemini-3.1-pro-preview packetizer
-> MJ/gpt-5.4 reviser
-> MJ/gpt-5.3-codex numeric auditor if needed
-> Cursor/gpt-5.4-extra-high verifier
```

권장 대상:

- 제출 직전 최종 문안 정리
- 마지막 승인 게이트

## Budget Rules

- `Orchestrator`: 1 call
- `Reviser`: 1 call
- `Numeric Auditor`: optional 1 call
- `Final Verifier`: 1 call
- 재수정이 필요하면 `Reviser 1 + Final Verifier 1`만 추가

즉, 기본 budget은 `3 calls`, numeric route는 `4 calls`, 최대치는 `5 calls`다.

## One-Line Rule

`Orchestrate on Gemini. Draft and audit on MJ_Codex. Accept only in Cursor High or Extra High.`

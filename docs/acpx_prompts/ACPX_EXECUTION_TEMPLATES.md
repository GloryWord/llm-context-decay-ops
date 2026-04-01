# ACPX Execution Templates

## Operating Stance

이 템플릿은 "기존 연구 문서에 교수 피드백을 반영하는 작업" 전용이다.
핵심 원칙은 다음과 같다.

- `composer-2`는 완전히 제거한다.
- 메인 `Orchestrator`는 항상 `Gemini`다.
- `Cursor AI`는 최종 검증에만 쓴다.
- `Reviser`와 `Numeric Auditor`는 `MJ_Codex`에서 실행한다.
- 같은 문서에 범용 리뷰어를 2명 이상 병렬로 붙이지 않는다.
- 한 문서당 총 루프는 최대 2회다.

## Runtime Legend

- `Gemini/...` = 메인 오케스트레이터
- `MJ/...` = `MJ_Codex`
- `Cursor/...` = `Cursor AI`

## Standard Artifacts

모든 실행은 아래 산출물만 주고받는다.

- `packet.yaml`
- `revised.md`
- `numeric_audit.yaml` if needed
- `verdict.yaml`

`packet.yaml`은 [CHANGE_LEDGER_TEMPLATE.yaml](/mnt/acpx_prompts/CHANGE_LEDGER_TEMPLATE.yaml) 형식을 따른다.

## Route A: General Revision

### Fixed Model Map

- `Orchestrator`: `Gemini/Auto Routing`
- `Reviser`: `MJ/gpt-5.4`
- `Final Verifier`: `Cursor/gpt-5.4-high`

### Verifier Upgrade Rule

- 일반 작업은 `Cursor/gpt-5.4-high`
- 제출 직전 또는 첫 검증에서 reasoning blocker가 남으면 `Cursor/gpt-5.4-extra-high`

### Call Order

1. `Orchestrator`가 교수 피드백을 `packet.yaml`로 압축한다.
2. `Reviser(MJ/gpt-5.4)`가 `revised.md`를 만든다.
3. `Final Verifier(Cursor/gpt-5.4-high)`가 `PASS/BLOCK`를 낸다.
4. `BLOCK`이면 blocker만 `Reviser`에게 되돌린다.
5. `Reviser`가 재수정한다.
6. `Final Verifier`가 한 번 더 판정한다.
7. 두 번째도 `BLOCK`이면 종료하고 사람 판단으로 넘긴다.

### Minimal ACPX Skeleton

아래는 실행 순서 템플릿이다. 실제 바이너리 이름은 네 환경에 맞게 바꾸면 된다.

```bash
# 0. Orchestrate
<gemini-runner> \
  --model auto-routing \
  --prompt-file acpx_prompts/ORCHESTRATOR_PROMPT.md \
  --doc <TARGET_MD> \
  --feedback <PROF_FEEDBACK_TXT> \
  > packet.yaml

# 1. Revise
<mj-codex-runner> \
  --model gpt-5.4 \
  --prompt-file acpx_prompts/REVISER_PROMPT.md \
  --packet packet.yaml \
  --doc <TARGET_MD> \
  > revised.md

# 2. Verify
<cursor-runner> \
  --model gpt-5.4-high \
  --prompt-file acpx_prompts/FINAL_VERIFIER_PROMPT.md \
  --packet packet.yaml \
  --revised revised.md \
  --loop-index 1 \
  > verdict.yaml

# 3. Retry only if verdict is BLOCK
<mj-codex-runner> \
  --model gpt-5.4 \
  --prompt-file acpx_prompts/REVISER_PROMPT.md \
  --packet packet.yaml \
  --doc <TARGET_MD> \
  --previous-blockers verdict.yaml \
  > revised_v2.md

<cursor-runner> \
  --model gpt-5.4-high \
  --prompt-file acpx_prompts/FINAL_VERIFIER_PROMPT.md \
  --packet packet.yaml \
  --revised revised_v2.md \
  --previous-blockers verdict.yaml \
  --loop-index 2 \
  > verdict_v2.yaml
```

## Route B: Numeric-Sensitive Revision

이 경로는 아래 중 하나라도 바뀔 때만 쓴다.

- 숫자
- 표
- threshold
- formula
- aggregation
- metric definition
- judge setting
- results에 직접 연결된 method description

### Fixed Model Map

- `Orchestrator`: `Gemini/Auto Routing`
- `Reviser`: `MJ/gpt-5.4`
- `Numeric Auditor`: `MJ/gpt-5.3-codex`
- `Final Verifier`: `Cursor/gpt-5.4-high`

### Verifier Upgrade Rule

- 일반 작업은 `Cursor/gpt-5.4-high`
- 제출 직전 또는 숫자/해석 blocker가 반복되면 `Cursor/gpt-5.4-extra-high`

### Call Order

1. `Orchestrator`가 `packet.yaml` 생성
2. `Reviser(MJ/gpt-5.4)`가 `revised.md` 생성
3. `Numeric Auditor(MJ/gpt-5.3-codex)`가 수치 정합성만 검사
4. `Numeric Auditor`가 `BLOCK`이면 그 blocker만 `Reviser`에게 전달
5. `Reviser`가 수치 관련 재수정
6. `Final Verifier(Cursor/gpt-5.4-high)`가 최종 판정
7. 필요하면 한 번만 재수정 후 재검증

### Minimal ACPX Skeleton

```bash
# 0. Orchestrate
<gemini-runner> \
  --model auto-routing \
  --prompt-file acpx_prompts/ORCHESTRATOR_PROMPT.md \
  --doc <TARGET_MD> \
  --feedback <PROF_FEEDBACK_TXT> \
  > packet.yaml

# 1. Revise
<mj-codex-runner> \
  --model gpt-5.4 \
  --prompt-file acpx_prompts/REVISER_PROMPT.md \
  --packet packet.yaml \
  --doc <TARGET_MD> \
  > revised.md

# 2. Numeric audit
<mj-codex-runner> \
  --model gpt-5.3-codex \
  --prompt-file acpx_prompts/NUMERIC_AUDITOR_PROMPT.md \
  --packet packet.yaml \
  --revised revised.md \
  > numeric_audit.yaml

# 3. Optional numeric repair if audit is BLOCK
<mj-codex-runner> \
  --model gpt-5.4 \
  --prompt-file acpx_prompts/REVISER_PROMPT.md \
  --packet packet.yaml \
  --doc <TARGET_MD> \
  --previous-blockers numeric_audit.yaml \
  > revised_v2.md

# 4. Final verify
<cursor-runner> \
  --model gpt-5.4-high \
  --prompt-file acpx_prompts/FINAL_VERIFIER_PROMPT.md \
  --packet packet.yaml \
  --revised revised_v2.md \
  --numeric-audit numeric_audit.yaml \
  --loop-index 1 \
  > verdict.yaml
```

## Session Policy

- `Gemini Orchestrator`: one-shot 실행 권장
- `MJ Reviser`: 문서별 one-shot 실행 권장
- `MJ Numeric Auditor`: persistent session 가능. 단, 매 실행마다 새 `packet.yaml`을 넣는다.
- `Cursor Final Verifier`: one-shot 실행 권장

이유는 세션 누적으로 이전 문서의 리뷰 문맥이 끼어드는 것을 막기 위해서다.

## Hard Stop Policy

- 한 문서당 총 agent call budget은 `5`를 넘기지 않는다.
- 같은 blocker가 두 번째에도 본질적으로 그대로면 종료한다.
- `PASS`가 나오면 polishing용 추가 리뷰를 금지한다.

## Recommended Retrofit To Your Current Stack

현재 네 구조를 유지하면서 최소 수정으로 바꾸면 아래처럼 된다.

```text
Gemini
  -> Auto Routing packetizer
MJ_Codex
  -> gpt-5.4 reviser
  -> gpt-5.3-codex numeric audit only when needed
Cursor AI
  -> gpt-5.4-high final verifier
```

삭제 대상:

- `composer-2`
- 범용 step1 reviewer
- 범용 step2 reviewer가 먼저 문서를 평가하고 step3가 다시 평론하는 구조

## What Not To Do

- `composer-2`를 문서 수정 루프에 넣지 말 것
- `Cursor AI`를 초안 작성이나 수치 감사에 쓰지 말 것
- `MJ_Codex` 범용 리뷰어를 2개 이상 병렬로 붙이지 말 것
- 이전 리뷰어의 장문 평가문을 다음 에이전트 입력으로 넘기지 말 것
- `조건부 승인`을 허용하지 말 것
- `수정문 없이 의견만` 출력하는 응답을 성공으로 처리하지 말 것

## MJ_Codex Model Selector

### Reviser

- `MJ/gpt-5.4`: 기본
- `MJ/gpt-5.2`: 큰 섹션 재구성
- `MJ/gpt-5.4-mini`: 아주 작은 수정

### Numeric Auditor

- `MJ/gpt-5.3-codex`: 기본
- `MJ/gpt-5.1-codex-max`: threshold, aggregation, method 충돌이 꼬였을 때
- `MJ/gpt-5.2-codex`: 중간 대안

### Cheap Triage Only

- `MJ/gpt-5.1-codex-mini`: 초경량 분류/패킷 점검

이 모델은 본문 수정과 최종 승인에는 권장하지 않는다.

## Gemini Orchestrator Selector

- `Gemini/Auto Routing`: 기본
- `Gemini/gemini-3.1-pro-preview`: 교수 피드백이 길고 충돌이 많을 때
- `Gemini/gemini-3-flash-preview`: 단순 packetize만 빠르게 할 때

# scripts/ — Workflow Bridge Guide

## Canonical Default (2026-04-04)
- **현재 기본 workflow 문서:** `../CODEX.md`
- 이 디렉토리의 스크립트는 **주 오케스트레이터가 아니라 legacy / bridge automation**이다.
- 기본 owner/orchestrator는 **Codex + OMX**다.
- 사용자는 원칙적으로 **초기 입력 요구사항 확인**과 **최종 blocker 검토**만 하면 된다.

---

## Recommended Default Workflow by Task Type

### 1) Research / Design
- 기본: `Codex + OMX`
- 권장 모드:
  - ambiguity 높음 → `$deep-interview`
  - 계획 합의 필요 → `$ralplan`
- 산출물:
  - `.omx/plans/prd-<slug>.md`
  - `.omx/plans/test-spec-<slug>.md`

### 2) Pipeline / Code
- 기본: `Codex + OMX`
- 권장 모드:
  - small scoped fix → solo execute
  - cross-module change → `$team` 또는 bounded subagent lanes
- 외부 reviewer는 로컬 검증 후 **필요할 때만** 붙인다.

### 3) Experiment Run
- 기본: `Codex + OMX`
- 권장 모드:
  - long-running execution → `$ralph`
- 핵심은 reviewer보다 **실행 증거와 재현성 로그**다.

### 4) Report / Thesis / Presentation
- 기본: `Codex + OMX`
- 필요 시 숫자/표 traceability를 먼저 확보한 뒤, 외부 reviewer 1명만 추가한다.
- 이 경우에만 아래 bridge scripts를 고려한다.

---

## Low-touch User Operating Model
시간이 없는 사용자를 위한 권장 운영 방식:

### User reviews only two moments
1. **초기 입력 요구사항**
   - 목표
   - in-scope / out-of-scope
   - 완료 조건
   - 비용 큰 실행 필요 여부
2. **최종 BLOCK 또는 escalation**
   - 왜 막혔는지
   - 어떤 evidence가 부족한지
   - 다음 선택지가 무엇인지

### Everything else is agent-owned
- Codex/OMX가 계획한다.
- Codex/OMX가 구현/실험/검증한다.
- 외부 reviewer는 좁은 packet으로만 호출한다.
- 사용자는 중간 progress chatter를 거의 보지 않아도 된다.

---

## Bridge Scripts: When To Use

### `claude_only/`
**용도:** finished deliverable에 대한 legacy cross-review bridge

사용 예:
```bash
bash scripts/claude_only/eval_all.sh <deliverable_path>
```

성격:
- Gemini(acpx) + Cursor 병렬 리뷰
- **기본 workflow가 아님**
- 로컬 evidence pack이 이미 있을 때만 사용

적합한 경우:
- 최종 보고서/문서에 외부 시각이 1회 더 필요할 때
- 로컬 검증은 끝났지만 narrative risk를 확인하고 싶을 때

부적합한 경우:
- 코드 수정 직후 매번 자동으로 돌리는 습관적 평가
- 산출물/summary/figure가 없는 상태에서의 “선평가”

### `gemini_only/`
**용도:** professor-feedback style 문서 수정용 ACPX loop

사용 예:
```bash
bash scripts/gemini_only/eval_all.sh <packet.yaml> <target.md> [keyword]
```

성격:
- MJ_Codex reviser
- optional numeric auditor
- Cursor final verifier
- 최대 2회 loop 후 BLOCK이면 human escalation

적합한 경우:
- 문서 수정 범위가 명확하고 packet으로 좁힐 수 있을 때
- 교수 피드백 반영, 발표문/보고서 문단 수정

부적합한 경우:
- 일반 코드 구현
- 실험 러너 수정
- repo 전체 오케스트레이션

---

## Evidence-first Rule
어떤 bridge script를 쓰더라도 먼저 아래를 확보한다.
- changed files
- commands run
- test output or run output
- 숫자/표 출처 파일
- unresolved risk

이 evidence pack 없이 받은 외부 리뷰는 **참고 의견**일 뿐이다.

---

## MJ_Codex Remote Collaboration Note
`gemini_only/` 내부 helper는 원격 `MJ_Codex` 세션을 사용할 수 있다.
하지만 이것은 **operator detail**이며, 기본 사용자 workflow의 중심이 아니다.
사용자는 원칙적으로 이 설정을 매번 신경 쓸 필요가 없다.

---

## Cautions
- **Gemini self-call 금지**: Gemini가 오케스트레이터일 때 자기 자신을 evaluator로 다시 부르면 loop가 꼬일 수 있다.
- **Missing artifact first**: summary JSON, figures, target docs가 없으면 reviewer보다 먼저 artifact 문제를 해결한다.
- **Legacy drift**: `claude_only/`, `gemini_only/`는 historical bridge이므로, 실제 인자와 경로는 스크립트 내용으로 재확인한다.

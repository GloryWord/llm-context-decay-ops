# OMX in this Capstone Domain

## 1. 핵심 결론
이 프로젝트에서 OMX는 “리뷰어를 많이 붙이는 도구”가 아니라,
**캡스톤 연구 작업을 라우팅하고, 상태를 유지하고, 검증 순서를 강제하는 운영 레이어**로 써야 합니다.

즉 OMX의 역할은 다음과 같습니다.
- 작업 유형 분류
- 근거 자료(evidence)를 기준으로 완료 조건 고정
- 장기 실행 상태 유지
- 구현 담당 / 검증 담당 분리
- 필요한 경우 작업 줄기를 나눠 각각 맡김
- 끝까지 해결되지 않는 막힘에서만 인간에게 올리기

사용자는 원칙적으로 다음 두 순간만 보면 됩니다.
1. 초기 요구사항 입력
2. 최종 BLOCK 또는 추가 판단 요청

바쁜 사용자는 먼저 `initial-input-and-final-blocker-only.md`를 보면 됩니다.
그 문서에는 **Codex 터미널에 무엇을 어떻게 입력하는지**가 먼저 적혀 있습니다.

---

## 2. 왜 기존 방식이 불편했는가
이 저장소의 과거 흔적을 보면 불편했던 이유가 뚜렷합니다.

### A. 기준 문서가 계속 바뀜
- `CLAUDE.md`: Claude orchestrator + Gemini + Cursor
- `GEMINI.md`: Gemini orchestrator + legacy helper split
- `scripts/README.md`: 또 다른 현재 구조
- `docs/acpx_prompts/*`: 교수 피드백 문서 수정용 규칙

즉, “누가 주인인지”가 계속 흔들렸습니다.

### B. 문서 수정 루프가 repo 전체에 과하게 적용됨
`docs/acpx_prompts/ACPX_OPERATING_SPEC.md`는 교수 피드백 문서 수정을 위한 룰에는 좋지만,
이 repo의 핵심인 실험 코드 / JSON / figure / report 전부를 다루기엔 범위가 좁습니다.

### C. 일반 검토가 많아도 근거 자료가 없으면 소용없음
같은 산출물을 두고 reviewer 평가가 크게 엇갈린 이유는,
리뷰어 수가 부족해서가 아니라 **입력 근거 자료가 부족했기 때문**입니다.

### D. 실행보다 평가가 먼저 달림
missing artifact 상태에서 보고서/숫자를 먼저 평가하려는 패턴이 있었고,
이 때문에 PASS/BLOCK이 prose 위주로 흔들렸습니다.

### E. hcom/acpx 운영 비용이 큼
과거 문서에서 보이듯 세션 reconnect, remote context injection, operator overhead가 컸습니다.

---

## 3. NoonAI workflow에서 가져와야 할 것
`noonai-dis-mcp-server`에서 가져올 핵심은 다음입니다.
- 오케스트레이터는 계획/라우팅에 집중한다.
- 실행자와 검증자의 책임을 섞지 않는다.
- 넘김은 근거 묶음(packet/evidence) 단위로 한다.
- PASS/BLOCK은 짧고 명확하게 낸다.
- 같은 막힘이 반복되면 사용자 판단 요청으로 올린다.
- 작업 기록 위치와 naming을 고정한다.

하지만 이 프로젝트는 SaaS가 아니라 capstone experiment repo이므로,
그 구조를 그대로 복붙하면 안 됩니다.

필수 수정점은 다음입니다.
- 문서 수정 1종 루프가 아니라 **설계 / 코드 / 실험 / 보고서** 라우팅이 필요함
- Gemini를 주 orchestrator로 둘 필요 없음
- Codex/OMX가 repo-local evidence를 직접 읽고 수정할 수 있으므로 **Codex + OMX를 중심**에 둬야 함

---

## 4. 이 프로젝트에서의 기본 역할 분담

### 기본 주인
- **Codex + OMX** = 작업 주인 / 오케스트레이터 / 검증 조율자

### 선택적으로 쓰는 외부 도구
- **Gemini CLI**: 긴 한국어 문서 논리, related work sanity check, 발표 narrative 점검
- **Cursor composer-2**: 구조/가독성/아키텍처 smell review

핵심은 외부 도구를 중심에 두지 않는 것입니다.
Codex/OMX workflow에서 `MJ_Codex`는 별도 외부 reviewer/helper가 아닙니다.
`MJ_Codex`를 보조 AI로 적는 것은 사실상 Codex를 자기 자신에게 다시 평가시키는 꼴이라 의미가 없습니다.
`MJ_Codex`가 필요하다면 그것은 maestro 쪽 legacy/전용 운영 문맥에서만 따로 다뤄야 합니다.

---

## 5. 작업 종류별 처리 방식

## 유형 A — Research / Design
예:
- 연구질문 수정
- 변수 범위 조정
- 실험 규모 축소
- Q4를 exploratory track으로 뺄지 결정

### OMX 역할
- 애매한 부분 정리
- 범위 고정
- 완료 기준 정의

### 추천 모드
- 애매한 부분이 큼 → `$deep-interview`
- 계획 합의 필요 → `$ralplan`

### 산출물
- `.omx/plans/prd-<slug>.md`
- `.omx/plans/test-spec-<slug>.md`

### 이유
설계가 안 굳은 상태에서 구현으로 바로 들어가면,
이 repo는 문서/코드/실험 drift가 매우 쉽게 발생합니다.

---

## 유형 B — Pipeline / Code
예:
- `src/evaluation/judge.py` 수정
- `src/models/open_router_request.py` 수정
- `scripts/run_experiment.py` 수정
- 테스트 추가/수정

### OMX 역할
- 구현 담당 분리
- 검증 담당 분리
- 필요 시 문서 동기화 담당 분리

### 추천 모드
- 범위가 작은 수정 → solo execute
- 여러 모듈에 걸친 수정 → `$team`

### 작업 분리 예시
- 1번 줄기: 구현 담당
- 2번 줄기: 검증 / 회귀 확인 담당
- 3번 줄기: 문서 동기화 담당 (필요할 때만)

### 이유
이 repo는 코드 수정 후 다음 drift가 자주 발생합니다.
- 문서 drift
- artifact naming drift
- summary/figure drift

따라서 병렬화의 목적은 “리뷰어 늘리기”가 아니라 **서로 다른 일을 섞지 않고 나누는 것**입니다.

---

## 유형 C — Experiment Run
예:
- 케이스 생성
- 본실험 rerun
- figure 재생성
- summary 재집계

### OMX 역할
- 실행 상태 유지
- checkpoint/resume 관리
- seed/model/env/output path 고정
- 실패 재시도 / terminal stop 관리

### 추천 모드
- `$ralph`

### 이유
실험은 reviewer보다 **실행 증거와 재현성 로그**가 중요합니다.
이 단계에서 generic reviewer를 여러 명 붙여도 큰 도움이 안 됩니다.

---

## 유형 D — Report / Thesis / Presentation
예:
- `docs/outputs/final_report.md`
- 발표용 narrative 수정
- 교수 피드백 반영

### OMX 역할
- 먼저 숫자/표의 출처와 연결 관계 확보
- 그 다음 필요 시 reviewer 1명만 추가

### 추천 모드
- 기본: solo Codex
- 근거 묶음(packet) 기반 문서 수정이 명확할 때만 `gemini_only` 경로 고려

### 이유
이 repo의 과거 문제는 “증거 없는 선평가”였습니다.
report/source/figure 연결이 먼저입니다.

---

## 6. workflow 결합 방식
이 프로젝트의 권장 흐름은 다음과 같습니다.

```text
[사용자 초기 입력]
    ↓
[Codex + OMX가 처리 방식 결정]
    ↓
[Codex + OMX가 내부 계획/구현/검증]
    ↓
[필요할 때만 외부 도구 호출]
    ↓
[완료 or BLOCK]
    ↓
[사용자에게 마지막 막힘만 보고]
```

핵심 포인트는 다음입니다.
- 외부 AI는 workflow의 중심이 아니다.
- 먼저 로컬 근거 자료를 확인한다.
- 기본 구조는 "작업 담당 1명 + 검증 담당 1명 + 필요 시 전문 도구 추가"다.
- Codex/OMX 처리 경로에는 `MJ_Codex`라는 별도 곁다리 평가자를 두지 않는다.
- PASS/BLOCK은 근거 자료가 있을 때만 의미가 있다.

---

## 7. Low-touch 운영 모델
시간이 없는 사용자를 위해,
이 프로젝트는 **중간 보고를 최소화**하는 방향이 맞습니다.

### 사용자가 보는 순간 1: Initial Input
여기서 말하는 Initial Input은 **사용자가 Codex 터미널에 직접 보내는 첫 메시지**입니다.
사용자는 시작 시 다음만 주면 됩니다.
- 목표
- 범위 내
- 범위 밖
- 완료 기준
- 참고 파일/문서

### 사용자가 보는 순간 2: Final Blocker
여기서 말하는 Final Blocker는 **Codex가 마지막에 올리는 막힘 보고**입니다.
막히면 아래만 받으면 됩니다.
- 무엇 때문에 막혔는지
- 이미 확인한 것
- 아직 확인 못한 것
- 선택지 A/B
- 권장안

### 그 사이
그 사이의 계획/구현/실험/검증은 Codex가 맡습니다.

---

## 8. OMX 기능별 권장 사용법

### `ralplan`
언제:
- 설계성 작업
- 여러 모듈에 걸친 변경
- 완료 기준이 중요한 작업

역할:
- PRD
- test spec
- 실행 전 범위 고정

### `$team`
언제:
- 구현/검증/문서 동기화를 나눠 맡길 가치가 있을 때

쓰지 말아야 할 때:
- 단순 문서 수정
- 단일 파일 hotfix
- reviewer만 늘리고 싶을 때

### `$ralph`
언제:
- 오래 걸리는 실험
- 재실행 + 체크포인트 관리
- figure/summary 다시 생성

핵심:
- 계속 밀고
- 근거 자료 모으고
- 끝까지 해결되지 않는 막힘에서만 멈춘다

### state / plans / memory
이 repo에서 OMX의 진짜 가치는 실행 상태를 계속 기억하는 데 있습니다.
- `.omx/plans/` → PRD / test spec
- `.omx/context/` → 작업 스냅샷 / 근거 묶음
- `.omx/state/` → 장기 실행 상태
- `.omx/notepad` → 왜 이 방향인지 메모

---

## 9. 외부 workflow와의 결합 원칙
### local evidence first
외부 reviewer 호출 전 항상 확보:
- changed files
- commands run
- test output
- 숫자/표 출처

### one owner, one verifier
generic reviewer 여러 명을 동시에 붙이지 않는다.

### 외부 도구 경로는 필요할 때만 사용
- `claude_only/` = 완성된 결과물을 한 번 더 교차 검토하는 경로
- `gemini_only/` = 교수 피드백 기반 문서 수정 경로
- `MJ_Codex` = Codex/OMX workflow에서는 별도 외부 경로로 두지 않음

### no evidence, no PASS
근거 자료가 없으면 `UNVERIFIED`다.

---

## 10. 추천 최종 운영 방식
이 프로젝트에서 OMX는 이렇게 써야 합니다.
- 오케스트레이션 중심
- 작업 종류별 라우터
- 장기 실행 상태 관리자
- 검증 순서 강제기
- 최종 blocker만 인간에게 올리는 필터

반대로 이렇게 쓰면 안 됩니다.
- reviewer를 잔뜩 붙이는 도구
- 모든 작업마다 외부 AI를 자동 호출하는 도구
- 교수 피드백용 ACPX 루프를 repo 전체에 강제하는 도구

결론적으로,
**좋은 multi-agent team은 “에이전트를 많이 붙이는 팀”이 아니라,
“증거가 생기는 순서대로 역할을 분리하는 팀”입니다.**

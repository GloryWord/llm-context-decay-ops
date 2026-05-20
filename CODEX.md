# LLM Context Decay Ops — CODEX.md

## 0. Role of this file
- 이 문서는 **Codex + OMX 전용 운영 브리프**다.
- 런타임 우선순위는 항상 `AGENTS.md`가 더 높다.
- `CLAUDE.md`, `GEMINI.md`, `docs/acpx_prompts/*`, `scripts/gemini_only/*`는 중요한 히스토리이지만, **Codex/OMX에서 무엇을 기본 워크플로우로 삼을지**는 이 문서를 기준으로 판단한다.
- 따라서 `scripts/claude_only/*`, `scripts/gemini_only/*`, ACPX 문서군은 **reference / opt-in legacy flow**로 취급한다.

---

## 1. Project identity

### Goal
이 저장소는 **캡스톤 디자인 / 학부 논문용 실험 저장소**다.
핵심 목표는 다음 질문들에 답하는 재현 가능한 실험 파이프라인을 유지·개선하는 것이다.

- **Q1**: 복수 규칙 준수율이 대화 턴 수 증가에 따라 어떻게 붕괴하는가?
- **Q2**: 규칙 유형별로 붕괴 순서가 다른가?
- **Q3**: benign vs adversarial(Crescendo-style) 조건에서 붕괴 시점과 속도가 달라지는가?
- **Q4**: 망각 vs 무력화 구분은 탐색적 과제이며, 기본 범위는 아님.

### Domain reality
이 프로젝트는 SaaS 기능 개발 저장소가 아니다. 작업 단위가 아래처럼 섞인다.
- 연구 설계/가설 정리
- 데이터셋 전처리/케이스 생성
- 실험 실행 및 체크포인트 관리
- 채점/집계/시각화
- 보고서/발표 문서 수정

즉, **단일 “코더 → 평가자” 루프만으로는 부족**하다. 작업 유형별 다른 경로가 필요하다.

### Key touchpoints
- `src/data_pipeline/`: 데이터 수집/전처리/실험 케이스 생성
- `src/evaluation/`: compliance scoring, judge, evaluation logic
- `src/compression/`: Phase 2 후보군
- `src/models/`: 모델 호출 경계
- `scripts/run_experiment.py`, `scripts/run_experiment_fast.py`: 실험 실행 진입점
- `scripts/generate_full_cases.py`, `scripts/generate_report.py`: 케이스 생성 및 리포트 집계
- `data/processed/`, `data/outputs/`: machine-readable artifact
- `docs/outputs/`: 보고서/figure 산출물
- `docs/multi-agent-working-history/`: 작업 기록

---

## 2. What went wrong in older workflows
이 저장소의 기존 흔적을 보면, 마음에 들지 않았을 가능성이 큰 이유가 명확하다.

### A. 워크플로우의 canonical source가 계속 바뀌었다
- `CLAUDE.md`: Claude orchestrator + Gemini + Cursor cross-check
- `GEMINI.md`: Gemini orchestrator + MJ_Codex + Cursor verifier
- `scripts/README.md`: 또 다른 “현재 구조” 설명
- `docs/acpx_prompts/ACPX_OPERATING_SPEC.md`: 교수 피드백 문서 수정 전용 ACPX 규칙

즉, **누가 오케스트레이터인지, 누가 최종 승인자인지, composer-2를 쓰는지 말지**가 문서마다 다르다.

### B. 도메인 mismatch가 있었다
`docs/acpx_prompts/ACPX_OPERATING_SPEC.md`는 본질적으로 **“교수 피드백을 받아 문서를 수정하는 루프”**에 최적화돼 있다.
하지만 이 저장소의 실제 핵심은 문서 수정만이 아니라:
- Python 파이프라인 수정
- 실험 재실행
- JSON/figure 검증
- 논문 수치 정합성 확인
이다.

즉, **문서 revision loop를 실험 엔지니어링 전체에 덮어씌운 점**이 어색했다.

### C. generic reviewer를 여러 명 붙여도 품질이 선형으로 좋아지지 않았다
히스토리상 같은 산출물을 두고도 평가가 꽤 달랐다.
- Gemini는 매우 높은 평가를 주는 반면
- Cursor gpt-5.4는 논리적 공백을 지적했고
- Codex 계열 평가는 산출물 부재 때문에 `PASS` 불가를 내리기도 했다.

이 패턴은 대개 **리뷰어 수가 부족해서가 아니라, 리뷰 입력이 넓고 검증 근거가 불충분해서** 생긴다.

### D. 검증 전에 평가가 먼저 달렸다
예: `experiment_summary.json`이나 `docs/experimental_design.md` 같은 참조 대상이 실제 workspace에 없거나 drift가 있는데도,
에이전트가 산출물을 평가하려고 했다.

이 프로젝트에서 **PASS/BLOCK은 prose가 아니라 evidence 기반**이어야 한다.

### E. 인프라 오버헤드가 컸다
`docs/hcom/acpx-integration-analysis.md`, `docs/hcom/acpx-reconnect-issue.md`가 보여주듯,
이전 방식은 hcom/acpx 세션 유지, reconnect, remote context injection 같은 운영 비용이 컸다.

사용자가 좋아했던 `noonai-dis-mcp-server`의 장점은 “역할 분리” 자체보다,
**경계가 명확하고 loop가 단순했다는 점**이다.

---

## 3. What to keep from the NoonAI workflow
`/Users/kawai_tofu/MHNCity/MCP_for_DIS/noonai-dis-mcp-server`에서 가져올 핵심은 아래다.

1. **오케스트레이터는 계획과 라우팅에 집중**한다.
2. **실행자와 검증자의 책임을 섞지 않는다.**
3. **handoff는 packet/artifact 단위**로 한다.
4. **PASS/BLOCK은 짧고 명확하게** 낸다.
5. **동일 blocker 반복 시 human escalation** 한다.
6. **작업 기록 위치와 naming을 고정**한다.

하지만 이 저장소에는 아래 변경이 필요하다.
- “문서 수정” 단일 루프가 아니라 **설계 / 코드 / 실험 / 보고서** 라우팅이 있어야 한다.
- Gemini가 main orchestrator일 필요가 없다.
- Codex/OMX가 repo-local evidence를 직접 읽고 수정할 수 있으므로, **Codex를 1차 orchestrator + executor**로 올리는 편이 자연스럽다.

---

## 4. Canonical Codex-first operating model

### North star
**Codex + OMX = 기본 오케스트레이터**

외부 AI는 필요할 때만 좁은 역할로 붙인다.
- **Gemini CLI**: 긴 문서 비교, 한국어 문체/논리 외부 시각, literature sanity check
- **Cursor composer-2**: 구조/가독성/아키텍처 smell review

둘 다 **보조 reviewer**일 뿐, 기본 pipeline의 중심이 아니다.

### Principle 1 — route by artifact, not by brand
작업을 “Gemini에게 보낼까 Cursor에게 보낼까”로 시작하지 말고,
항상 아래 순서로 분류한다.

1. 이 작업의 산출물은 무엇인가?
   - 계획 문서?
   - Python 코드?
   - 실험 결과(JSONL/figures)?
   - 보고서/발표 자료?
2. 어떤 증거가 있어야 완료라고 말할 수 있는가?
3. 그 증거를 누가 가장 싸고 정확하게 만들 수 있는가?

### Principle 2 — local evidence first
외부 reviewer를 부르기 전에 Codex가 먼저 아래를 확보한다.
- changed files
- 관련 테스트 출력
- 관련 JSON/figure/summary 경로
- unresolved risk

**증거 묶음 없이 받은 외부 평가는 참고 의견일 뿐 gate가 아니다.**

### Principle 3 — one owner, one verifier, optional specialist
기본 형태:
- **Owner**: Codex/OMX
- **Verifier**: Codex verifier/test lane 또는 evidence 기반 reviewer 1명
- **Specialist(optional)**: Gemini 또는 composer-2 중 1명

동시에 generic reviewer를 2명 이상 병렬로 붙이지 않는다.

### Principle 4 — PASS/BLOCK only after replication or traceability
다음 중 하나라도 없으면 `PASS`가 아니라 `UNVERIFIED`로 취급한다.
- 테스트 재현
- 숫자/표 traceability
- figure ↔ summary ↔ report 연결
- 참조 파일 실존 확인

---

## 5. Route map for this repository

### Route A — Research / Design
**언제:**
- RQ 수정
- 변수 설계 변경
- 실험 범위 축소/확장
- Q4 같은 exploratory topic 추가 검토

**기본 모드:**
- ambiguous하면 `$deep-interview`
- 계획 합의가 필요하면 `$ralplan`

**필수 산출물:**
- `.omx/plans/prd-<slug>.md`
- `.omx/plans/test-spec-<slug>.md`
- scope / out-of-scope / evidence / acceptance criteria

**규칙:**
- 설계가 안 굳었으면 implementation으로 바로 넘어가지 않는다.
- Q4는 기본값이 아니라 opt-in exploratory track으로 둔다.

---

### Route B — Pipeline / Code
**언제:**
- `src/`, `scripts/`, `tests/` 변경
- 데이터 로딩/케이스 생성/평가/시각화 로직 수정

**기본 모드:**
- 작은 수정: solo Codex execute
- cross-module 수정: `$team` 또는 bounded native subagent lanes

**추천 lane 구성:**
- Lane 1: implementation owner
- Lane 2: verification/tests/regression owner
- Lane 3: docs sync owner (필요할 때만)

**완료 기준:**
- 코드 수정
- 테스트/검증 출력
- 문서 drift 정리(있다면)

**기본 검증 명령:**
- 의존성 설치: `python3 -m pip install -r requirements.txt`
- 테스트 실행: `python3 -m pytest`

**주의:**
- 이 프로젝트는 문서와 코드 drift가 자주 있었다.
- 코드가 바뀌면 최소한 관련 문서 경로/파일명/기본 입력 예시는 함께 재검토한다.

---

### Route C — Experiment Run
**언제:**
- 케이스 생성
- 본실험/파일럿 실행
- figure 및 summary 재생성

**기본 모드:**
- `$ralph` 단일 owner loop 권장
- 필요 시 monitor/verifier sidecar만 추가

**실행 전에 반드시 고정할 것:**
- input artifact 경로
- 모델/환경변수
- seed / repeat count
- output directory
- resume/checkpoint 기준

**필수 로그:**
- 실행 명령어
- 환경변수 핵심값(비밀 제외)
- 생성/수정된 산출물 경로
- 실패/재시도 사유

**이 route에서는 generic reviewer보다 실행 증거가 우선**이다.

---

### Route D — Report / Thesis / Presentation
**언제:**
- `docs/outputs/*.md`
- 최종 보고서
- 발표 자료 초안
- 연구 설계 문서 정리

**기본 모드:**
- Codex owner가 초안/수정
- 숫자/표가 바뀌면 numeric audit 필수
- 외부 reviewer는 최대 1명만 추가

**필수 evidence pack:**
- 어떤 표/문장이 어떤 파일을 근거로 하는지
- `experiment_summary.json` 또는 대응 machine-readable source
- 관련 figure 경로
- 관련 코드/집계 로직 위치

**룰:**
- summary/figure/source file이 없으면 강한 결론 문장을 쓰지 않는다.
- reviewer에게 긴 prose 전체를 던지지 말고, evidence pack만 준다.

---

## 6. Canonical artifact contract

### A. Task snapshot
권장 경로:
- `.omx/context/<slug>-snapshot.md`

필수 항목:
- task statement
- why now
- in-scope / out-of-scope
- touched files
- expected evidence
- open risks

### B. Plan artifacts
권장 경로:
- `.omx/plans/prd-<slug>.md`
- `.omx/plans/test-spec-<slug>.md`

### C. Evidence pack
권장 경로:
- `.omx/context/<slug>-evidence.md`

필수 항목:
- changed files
- commands run
- test outputs
- numbers/figures source map
- unresolved issues

### D. Human-readable work log
권장 경로:
- `docs/multi-agent-working-history/YYYY-MM-DD/HHMM_<slug>.md`

이 저장소의 기존 히스토리 관례를 유지하되,
**리뷰 전문을 길게 붙이는 대신 decision + evidence + next action만** 기록한다.

---

## 7. External AI usage policy

### Gemini CLI — allowed, but narrow
적합한 용도:
- 긴 한국어 문서 논리 점검
- literature survey / related work sanity check
- 발표용 narrative 흐름 검토

부적합한 용도:
- repo 전체의 primary orchestrator
- 근거 파일 없이 숫자 검증
- 코드 수정의 최종 승인자

### Cursor composer-2 — allowed, but not a gate
적합한 용도:
- 구조적 readability feedback
- 모듈 경계/리팩토링 아이디어
- 문서 구성/슬라이드 흐름 코멘트

부적합한 용도:
- PASS/BLOCK 단독 결정
- 수치 감사자
- 같은 unchanged artifact에 대한 2차 generic review

### External review rule
외부 AI를 쓰더라도 반드시 **review packet**을 좁게 만든다.
포함할 것:
- 목표
- 변경 파일
- evidence pack 핵심만
- 질문 1~3개

포함하지 말 것:
- 이전 리뷰어 장문 prose 전체
- repo 전체 dump
- 이미 기각된 blocker 재전달

---

## 8. Verification gates

### Minimum gate for any completion claim
- 파일 수정 확인
- 관련 검증 명령 실행
- 출력 읽고 해석
- 남은 리스크 명시

### Extra gate for numeric/report changes
- 숫자 출처가 machine-readable artifact로 trace되는가?
- 표/그래프 설명이 실제 산출물과 일치하는가?
- 누락 artifact가 있으면 `PASS` 대신 `UNVERIFIED`

### Extra gate for experiment reruns
- seed/repeat/model/env 기록
- checkpoint/resume 여부 기록
- 이전 결과와 비교 가능하도록 경로 고정

### Escalation rule
같은 blocker가 2번 반복되면 human escalation.
특히 아래는 즉시 보고:
- missing artifact 때문에 검증 불가
- 비용 큰 API run 필요
- destructive cleanup 필요
- 문서 주장과 코드/산출물 사실이 충돌

---

## 9. Known drift / do not trust blindly
이 저장소에는 historical drift가 있다. 아래는 항상 실제 파일 기준으로 재확인한다.

- `CLAUDE.md`, `GEMINI.md`, `scripts/README.md`의 workflow 설명은 서로 완전히 일치하지 않는다.
- `docs/acpx_prompts/*`는 교수 피드백 문서 수정 루프 기준이다.
- `docs/experimental_design.md`는 현재 repo에 없을 수 있다.
- `experiment_cases.jsonl` vs `experiment_cases_full.jsonl` 같은 naming drift가 있었다.
- reviewer가 참조하는 요약 JSON/figure가 git에 없을 수 있다.

**따라서 이 repo에서 truth priority는 아래 순서다.**
1. 실제 코드
2. 실제 machine-readable outputs
3. 현재 task의 evidence pack
4. 최신 work log
5. legacy 운영 문서

---

## 10. Recommended default workflow for Codex

### Small scoped task
1. task snapshot
2. solo execute
3. local verification
4. concise work log

### Cross-module engineering task
1. `$ralplan`으로 scope/test shape 고정
2. `$team` 또는 bounded subagent lanes로 구현/검증 분리
3. leader가 evidence pack 통합
4. 필요 시 external reviewer 1명만 추가

### Experiment + report task
1. 설계/범위 고정
2. `$ralph`로 실행 및 산출물 생성
3. numeric audit
4. 보고서 반영
5. traceability check

---

## 11. Final mindset
이 프로젝트에서 좋은 multi-agent team은
**“에이전트를 많이 붙이는 팀”이 아니라,**
**“증거가 생기는 순서대로 역할을 분리하는 팀”**이다.

Codex/OMX는 이 저장소에서 다음 역할을 맡는다.
- 기본 orchestrator
- 기본 implementer
- 기본 verifier coordinator

Gemini와 composer-2는 필요할 때만 좁게 붙인다.

이 문서의 목표는 화려한 agent mesh가 아니라,
**캡스톤 논문에 필요한 설계-구현-실험-보고 루프를 가장 적은 혼선으로 굴리는 것**이다.

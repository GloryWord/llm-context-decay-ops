# Cursor Agent Evaluation — codex

- **Date**: 2026-04-01 01:12
- **Deliverable**: docs/outputs/final_report.md
- **Model**: gpt-5.3-codex
- **Role**: codex

## Result

핵심 근거를 확보했고, 이제 요청하신 5개 축으로 `파일:라인` 중심의 감사 결과를 정리해 드리겠습니다. 특히 수치 검증은 현재 저장소 상태에서 가능한 범위와 불가능한 범위를 분리해서 명확히 표기하겠습니다.## 저수준 감사 결과 (엄격 검증)

### 먼저 결론
- **현재 워크스페이스에는 `experiment_summary.json`이 존재하지 않아** 요청하신 `(1) 보고서 숫자 1:1 대조`를 완전 수행할 수 없습니다.
- 따라서 수치 검증은 **검증 가능/불가를 분리**해 보고합니다.
- 나머지 `(2)~(5)`는 코드 기준으로 `파일:라인`까지 확인했습니다.

---

### 1) 수치 검증 (보고서 ↔ `experiment_summary.json`)

- **치명적 불일치(검증 불가 상태)**  
  - `scripts/generate_report.py:441`에서 `docs/outputs/experiment_summary.json`를 생성하도록 되어 있으나, 현재 저장소에는 해당 파일이 없습니다(경로 미존재).  
  - `scripts/eval_cursor.sh:59`는 이 파일과의 1:1 대조를 감사 기준으로 강제하지만, 현재 상태에서는 실행 불가입니다.
- **경로 불일치 동반**  
  - 보고서가 참조하는 `figures/...` 산출물도 현재 `docs/outputs/` 하위에 존재하지 않습니다(산출물 부재 상태).

- **보고서 텍스트 자체 산술 점검에서 발견된 모순**
  - 보고서 1.3의 `1,540 runs × avg 7.1 turns = 10,890`은 엄밀히는 성립하지 않습니다.  
    (`1,540 × 7.1 = 10,934`)  
  - 이 값은 **평균 턴이 약 7.07일 때** `10,890`이 되므로, 표기 방식(곱셈식)이 부정확합니다.

---

### 2) 코드 경로 검증 (import/path 실존성)

- **실행 경로 리스크(파일 참조 실패 가능)**
  - `scripts/run_experiment.py:83`  
    - 기본 입력: `data/processed/experiment_cases_full.jsonl`  
    - 현재 저장소에는 해당 파일 없음 → 기본 실행 즉시 실패 가능.
  - `scripts/run_experiment_fast.py:67`  
    - 동일 기본 케이스 파일 의존.
  - `scripts/generate_report.py:416`  
    - 기본 입력: `data/outputs/main_experiment/results_*.jsonl`  
    - 현재 저장소에는 결과 JSONL 부재 → 리포트 생성 실패/빈 결과.

- **import 경로 자체는 대체로 정상**
  - `scripts/run_experiment.py:37` → `src.evaluation.compliance_scorer` 실제 존재.
  - `scripts/run_experiment_fast.py:30` → 동일.

---

### 3) 엣지 케이스 누락 (division by zero / empty / None)

- **High: `None` 응답 미방어**
  - `scripts/run_experiment_fast.py:98`에서 API 응답 `content`를 그대로 반환,  
    `scripts/run_experiment_fast.py:134`에서 `len(response)` 수행  
    → `content=None`이면 `TypeError`.
  - 동일 패턴:  
    `scripts/run_experiment.py:133`, `scripts/run_experiment.py:212`
- **High: 빈 `turn_results` 인덱싱**
  - `scripts/generate_report.py:198`  
    - `best["turn_results"][0]` 직접 인덱싱  
    - 실패 run/비정상 레코드 포함 시 `IndexError` 가능.
- **Medium: 예외 은닉으로 누락 데이터 생성**
  - `scripts/run_experiment_fast.py:230`  
  - `scripts/run_experiment_fast.py:297`  
    - `asyncio.gather(..., return_exceptions=True)` 후 예외 객체 검증/재시도/실패 마킹 없음.
- **Medium: 정규식 ReDoS 가능성**
  - `src/evaluation/compliance_scorer.py:161`  
    - 외부 입력 패턴에 대해 `re.search(pattern, response)`를 직접 수행(타임아웃/복잡도 제한 없음).

---

### 4) 재현성 점검 (seed/checkpoint/deterministic)

- **좋은 점**
  - seed 고정: `scripts/generate_full_cases.py:317`, `scripts/generate_full_cases.py:379`
  - checkpoint 복원:  
    `scripts/run_experiment_fast.py:153-163`,  
    `scripts/run_experiment.py:240-251`
  - sampling 고정: inference/judge 모두 `temperature=0.0`  
    (`scripts/run_experiment.py:115`, `scripts/run_experiment_fast.py:85`, `src/evaluation/compliance_scorer.py:302`)
- **부족한 점**
  - 외부 API 비결정성(백엔드/모델 리비전 변화)에 대한 **버전 고정 로그/스냅샷 부재**.
  - 실패 run이 예외 은닉으로 누락될 수 있어(위 230/297) 동일 seed라도 완전 재현성 저하.

---

### 5) 보안 점검 (키 노출/하드코딩/인젝션)

- **High: 하드코딩된 외부 인프라 엔드포인트**
  - `scripts/run_experiment.py:56`
  - `scripts/run_experiment_fast.py:48`
  - `src/models/open_router_request.py:25`
  - 공인 IP/포트가 코드 기본값으로 노출됨.
- **Medium: 로컬 호출에도 Authorization 헤더 전송 가능**
  - `scripts/run_experiment.py:108`
  - `scripts/run_experiment_fast.py:78`
  - 기본 설정상 로컬 vLLM에도 `OPENROUTER_API_KEY` 계열 토큰이 헤더로 실릴 수 있어 노출면 확대.
- **Medium: 입력 기반 정규식 실행**
  - `src/evaluation/compliance_scorer.py:161`
  - 악성 패턴 주입 시 성능 공격 가능(ReDoS).

---

## 요약 판단
- **현재 상태는 수치 감사의 핵심 전제(`experiment_summary.json`)가 깨져 있어 PASS 불가**입니다.
- 코드 품질 측면에서는 특히 **`None` 응답 처리, 예외 은닉, 하드코딩 엔드포인트** 3건이 우선 수정 대상입니다.

원하시면 다음 답변에서 바로
- `None` 방어,
- `gather` 예외 처리/실패 마킹,
- 로컬 호출 시 Authorization 헤더 제거
까지 패치 포인트별로 짧게 제시하겠습니다.

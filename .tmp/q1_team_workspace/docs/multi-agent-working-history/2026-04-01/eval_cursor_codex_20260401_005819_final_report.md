# Cursor Agent Evaluation — codex

- **Date**: 2026-04-01 01:04
- **Deliverable**: docs/outputs/final_report.md
- **Model**: gpt-5.3-codex
- **Role**: codex

## Result

## 저수준 감사 결과 (엄격 검증)

### 1) 수치 검증: `final_report.md` ↔ `experiment_summary.json`

표 기반 핵심 수치(3.1, 3.2)는 대체로 **일치**합니다.  
다만 아래 **명시적 불일치**가 있습니다.

- **불일치 1**: `docs/outputs/final_report.md:128`  
  - 주장: R=1 격차가 `44-69pp`  
  - 실제(표 3.1): `50.0pp, 50.0pp, 68.9pp, 88.9pp` (`docs/outputs/final_report.md:151-154`, 원천 `docs/outputs/experiment_summary.json`의 `condition_means`)
- **불일치 2**: `docs/outputs/final_report.md:216`  
  - 주장: R=1 adversarial collapse `0-33%`  
  - 실제(표 3.1): `50.0%, 50.0%, 31.1%, 11.1%` (`docs/outputs/final_report.md:151-154`)
- **불일치 3 (범위 과소기재)**: `docs/outputs/final_report.md:233`  
  - 주장: adversarial 붕괴 `T3-T8`  
  - 실제 CT 범위: `T4.2 ~ T10.0` (`docs/outputs/final_report.md:172-175`, `docs/outputs/experiment_summary.json:170-211`)

추적성(1:1 대조) 관점의 문제도 있습니다.

- **검증불가(요약 JSON에 근거 없음)**: `docs/outputs/final_report.md:37, 247`의 `Runtime ~87 min`
- **검증불가(요약 JSON에 근거 없음)**: `docs/outputs/final_report.md:103, 223, 249-251`의 Judge 모델/완료시각/모델명 세부
- 참고: `10,890 responses`, `29,700 auto-checks`, `10,890 judge calls`는 설계/집계상 정합적이나, 이는 `experiment_summary.json` 단독이 아니라 케이스/결과 파일 기반 산술로 확인되는 항목입니다.

---

### 2) 코드 경로 검증 (import/path)

- **실패 경로/깨진 import는 이번 점검 범위에서 미발견**  
  - 예: `src/data_pipeline/load_datasets.py`의 `from src.data_pipeline.generate_experiment_cases import generate_cases`는 실제 파일/함수 존재
  - 보고서 그림 경로(`figures/q1...`, `q2...`, `q3...`, `heatmap...`)도 실제 파일 존재 확인

---

### 3) 엣지 케이스 누락

- **예외 삼킴으로 실패 은닉**: `scripts/run_experiment_fast.py:230`  
  - `asyncio.gather(..., return_exceptions=True)` 후 예외 객체를 검사/재시도/기록하지 않아, 일부 run 실패가 조용히 누락될 수 있음
- **동일 문제(배치 judge)**: `scripts/run_experiment_fast.py:297`  
  - judge 실패가 누락되어 최종 `judge_status=complete`와 실제 상태가 불일치할 위험
- **None 응답 방어 미흡**: `scripts/run_experiment_fast.py:98, 134` / `scripts/run_experiment.py:133, 212`  
  - API가 `content=null` 반환 시 `len(response)` 등에서 런타임 오류 가능
- **입력 파일 부재 방어 미흡**: `scripts/run_experiment_fast.py:174`  
  - `CASES_FILE` 존재 확인 없이 바로 open

---

### 4) 재현성 점검

- **좋은 점**: 케이스 생성 seed 고정 (`scripts/generate_full_cases.py:317, 379`)  
- **좋은 점**: checkpoint 복원 로직 존재 (`scripts/run_experiment_fast.py:153-163`, `scripts/run_experiment.py:240-251`)  
- **리스크**:
  - 동시 실행 + 예외 은닉(`run_experiment_fast.py:230, 297`)으로 재실행 시 결과 완전성 흔들림
  - 외부 API 의존 judge/inference는 `temperature=0`이어도 공급자측 비결정성 가능 (코드상 완전 deterministic 보장 장치 없음)

---

### 5) 보안 점검

- **민감 인프라 노출**: `docs/outputs/final_report.md:35, 244`  
  - 공인 IP/포트(`210.179.28.26:18000`) 문서 직접 노출
- **하드코딩된 외부 엔드포인트**:  
  - `scripts/run_experiment_fast.py:48`  
  - `scripts/run_experiment.py:56`  
  - `src/models/open_router_request.py:25`  
  운영환경 분리/비밀 관리 측면에서 취약
- **API 키 전송 경로 최소화 미흡**: `scripts/run_experiment_fast.py:50, 78`, `scripts/run_experiment.py:62, 108`  
  - 로컬 vLLM 호출에도 `OPENROUTER_API_KEY`를 Authorization 헤더로 전송 가능(기본값 구성상), 키 노출면 확대 가능

---

원하시면 다음으로, 위 지적사항을 기준으로 **수정 우선순위(즉시/단기/중기)**와 함께 패치 포인트까지 정리해드리겠습니다.

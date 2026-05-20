# Final Report Feedback Diagnosis

## 핵심 결론

- 교수님 피드백은 타당하다. 기존 `docs/outputs/final_report.md`는 "무엇을 평균냈는가"를 충분히 설명하지 않았다.
- `rule_count`는 모든 조합 평균이 아니라 `scripts/generate_full_cases.py`에 정의된 curated `rule_set_variant` 평균이다.
- turn 데이터는 실험 중 즉흥 생성한 것이 아니라 `seed=42`로 만든 `data/processed/experiment_cases_full.jsonl`의 고정 case를 5회 반복 실행한 것이다.
- Q1/Q3 그래프는 고정된 `turn_count` 조건이 아니라, 해당 turn까지 도달한 run 전체를 pooled average한 그림이다.
- Q2 그래프는 benign/adversarial과 rule_count를 분리하지 않고 pooled average한 그림이라 해석 범위를 낮춰야 한다.

## 교수님 질문에 대한 바로답변

### 1. "rule_count=3은 모든 3개 조합 평균인가?"

아니다. 이번 실험은 전수 조합이 아니라 미리 정한 variant만 썼다.

- `rule_count=1`: 3 variants
- `rule_count=3`: 3 variants
- `rule_count=5`: 3 variants
- `rule_count=7`: 2 variants

### 2. "2개 규칙 조건도 있나?"

없다. 이번 실험의 `rule_count` 수준은 `1, 3, 5, 7`뿐이다.

### 3. "turn 데이터가 고정이라는 게 무슨 뜻인가?"

- `scripts/generate_full_cases.py`가 `seed=42`로 308개 case를 생성
- 결과는 `data/processed/experiment_cases_full.jsonl`에 저장
- 5회 반복은 같은 case 파일 재실행
- 즉, turn 내용은 미리 고정돼 있고 반복마다 다시 샘플링하지 않는다

## workflow 평가

### 견고한 점

- deterministic case generation
- full raw result `data/outputs/main_experiment/fast_results_*.jsonl` 1540 rows 존재
- `docs/outputs/experiment_summary.json`와 핵심 수치 정합

### 약한 점

- 발표용 보고서가 집계 단위를 충분히 설명하지 못함
- judge 모델 메타데이터가 raw artifact에 남지 않음
- partial result file(`results_*.jsonl`, 54 rows)가 함께 있어 혼동 소지
- figure semantics가 코드에 비해 과감하게 해석되어 있음

## 바로 필요한 대응

1. 발표 자료에 "한 점 = 무엇의 평균인가" 슬라이드 추가
2. `rule_set_variant` 표 추가
3. `experiment_cases_full.jsonl`에서 고정 turn 예시 1개 제시
4. Q1/Q3는 pooled turn trajectory라고 명시
5. Q2는 전체 pooled trend로 격하해서 설명

## 이번 수정

- `docs/outputs/final_report.md`에 데이터 단위, rule-set variant, fixed case 설명, figure 읽는 법을 추가했다.
- 상세 진단 메모는 `docs/outputs/final_report_feedback_diagnosis.md`에도 저장했다. 단, 이 경로는 `.gitignore` 대상이다.

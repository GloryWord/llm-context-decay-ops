# Cursor Agent Evaluation — composer2

- **Date**: 2026-04-01 17:09
- **Deliverable**: GEMINI.md
- **Model**: composer-2
- **Role**: composer2

## Result

Connection lost, reconnecting...
Retry attempt 1...

저장소를 직접 살펴본 결과를 바탕으로, 제시하신 **CLAUDE.md 성격의 프로젝트 개요·운영 규칙**과 **실제 코드·산출물(`docs/outputs/`)**을 함께 기준으로 평가했습니다.

---

## (1) 데이터 정합성 — **등급: 중**

**근거**
- `docs/outputs/experiment_report.md`와 `docs/outputs/experiment_summary.json`은 **직접 대조 시 일치**합니다. 예: `total_runs: 1540`, `R1_T10_adversarial`의 mean ≈ 0.311, `n: 45`, 임계값 블록의 `R3_adversarial` DO/CT 등이 보고서 표와 JSON이 같은 출처로 정리되어 있습니다.
- 반면 **문서 ↔ 코드** 불일치가 있습니다. 개요 표에는 행동 규칙 채점이 “DeepSeek **V3**”로 적혀 있는데, `src/evaluation/compliance_scorer.py`의 판정 모델 기본값은 `deepseek/deepseek-**r1**`(환경변수로 변경 가능)입니다. 수치 검증과 별개로 **메타데이터 신뢰도**가 깎입니다.
- 기본 파이프라인 진입점 `load_datasets.py`는 `configs/preprocess.yaml`을 전제로 하는데, **현재 워크스페이스에는 해당 YAML이 없습니다**(레거시 삭제 이력과 부합). 재현·정합 검증을 막는 요인입니다.
- 데이터 플로우 설명은 `sample_cases_v4.jsonl`(10건)과 `experiment_cases_full.jsonl`(본 실험)이 **한 다이어그램에만 섞여 읽히기 쉬워**, “무엇이 최종 실험의 진실의 원천인지”가 한 번 더 정리될 필요가 있습니다.

---

## (2) 코드 구조 — **등급: 상**

**근거**
- `src/data_pipeline`, `src/evaluation`, `src/models`, `src/utils`, `scripts/`로 **역할 분리가 분명**하고, 메인 실험(`run_experiment.py`), 고속 러너(`run_experiment_fast.py`), 리포트(`generate_report.py`), 풀 케이스 생성(`generate_full_cases.py`)이 **스크립트 단위로 나뉘어** 있습니다.
- **중복·이중화**는 있습니다: `generate_experiment_cases.py`(YAML·전처리 기반)와 `generate_full_cases.py`(팩토리얼 설계 단독)가 **케이스 생성 경로를 둘로 유지**합니다. 의도적 분기일 수 있으나, 신규 기여자에게는 “어느 경로가 공식인지”를 한 줄로 고정해 두는 편이 좋습니다.

---

## (3) 파이프라인 일관성 — **등급: 중**

**근거**
- **의도된 흐름**은 분명합니다: 케이스 JSONL → `run_experiment*` → 결과 JSONL → `compliance_scorer`(+ 비동기 judge) → `generate_report.py` → `docs/outputs` 및 figures.
- **누락·불일치**: `configs/preprocess.yaml` 부재로 **문서에 적힌 `python -m src.data_pipeline.load_datasets --config ...` 경로가 그대로는 성립하기 어렵습니다**. 압축 파이프라인(`src/compression/`)은 “Phase 2 보류”와 문서가 맞지만, 파일명이 `experiment_cases.jsonl` vs `experiment_cases_full.jsonl`로 **문서마다 기준이 갈립니다**.
- 다단계 **평가 게이트**(eval 스크립트, working-history)는 **운영 규칙**으로는 강하지만, 코드 레벨의 단일 `make`/CI로 강제되지는 않습니다.

---

## (4) 논리적 일관성 — **등급: 중**

**근거**
- 연구 질문(Q1–Q3), 요인(`rule_count`×`turn_count`×`attack_intensity`), 반복 5회, 모델 조합은 **서로 모순되지 않고** 설계서 형태로 읽힙니다.
- **과대 해석**: 제출 텍스트만 보면 **단정적 결론**을 데이터에서 끌어다 쓰지는 않습니다. 다만 `docs/outputs`의 DO/CT 같은 지표는 **정의(80%/50%)에 민감**하므로, 논문/보고서에서는 “임계 정의와 민감도”를 본문에 박아 두지 않으면 독자가 과해석할 여지가 있습니다(코드 문제라기보다 **서술·방법론** 이슈).
- 문서의 “V3 판정” vs 코드의 “R1”은 **연구 재현성 서술**과 충돌하므로, 논리 일관성 측면에서 감점 요인입니다.

---

## (5) 코드 품질 — **등급: 중**

**근거**
- **재현·안정성**: `run_experiment.py`에 **체크포인트/재개**, API **재시도**, `temperature=0` 등이 있습니다. `generate_full_cases.py`는 `seed`(기본 42)와 변형별 파생 시드를 사용합니다.
- **타입 힌트**: 일부 스크립트와 함수에만 있고, `compliance_scorer` 등 핵심 모듈은 **딕셔너리 중심**이라 정적 타입으로는 덜 단단합니다.
- **에러 처리**: judge·langdetect 경로에 예외·폴백이 있으나, 실패 시 실험 전체를 어떻게 표기할지(부분 NA 등)는 **리포트 스키마와 한번 더 맞추는 편**이 좋습니다.
- **테스트**: `tests/test_compliance_scorer.py` 등으로 **채점 로직은 부분 검증**되나, E2E·`run_experiment`·리포트 생성에 대한 자동 테스트는 제한적입니다.

---

## (6) 개선 제안 — **등급: 중**  
(프로젝트가 이 축에서 “이미 잘 갖춘 정도”보다는 **남은 과제의 구체성**으로 평가)

**구체적 제안**
| 영역 | 제안 |
|------|------|
| 문서·재현 | `configs/preprocess.yaml`을 복구하거나, `load_datasets` 기본 경로/문서를 **현재 단일 소스(`generate_full_cases`)**에 맞춰 정리. Judge 모델명을 **코드 기본값과 동일**하게 통일. |
| 파이프라인 | `experiment_cases.jsonl` / `experiment_cases_full.jsonl` **명명 규칙**을 한 페이지에 표로 고정. |
| 테스트 | `generate_report.py`의 집계 로직에 대한 **골든 파일 테스트**(작은 JSONL 입력 → 기대 `experiment_summary.json` 스냅샷). |
| 품질 | 공개 API 경계에 **Pydantic/dataclass** 도입으로 rule/result 스키마 고정, 또는 최소한 JSON 스키마 문서화. |
| 성능 | 이미 fast 러너가 있으므로, 문서에 **언제 어떤 스크립트를 쓰는지** 성격 차이를 표로 명시. |

---

### 요약 표

| 항목 | 등급 |
|------|------|
| (1) 데이터 정합성 | 중 |
| (2) 코드 구조 | 상 |
| (3) 파이프라인 일관성 | 중 |
| (4) 논리적 일관성 | 중 |
| (5) 코드 품질 | 중 |
| (6) 개선 제안(개선 필요도·구체성) | 중 |

**종합**: 산출물 **수치 정합성**(보고서↔JSON)은 샘플 검증상 **양호**하나, **문서·설정·케이스 파일명**이 한 축으로 묶이지 않아 전체를 **상**으로 보기 어렵습니다. 구조는 **상**, 운영·재현·메타데이터 정리는 **중** 수준으로 보는 것이 타당합니다.

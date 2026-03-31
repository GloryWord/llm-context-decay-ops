# Phase 1 v2: Experiment Redesign — Rule Count Scaling & Token Threshold

**Date:** 2026-03-24
**Status:** 실행 완료, 결과에 심각한 문제 다수 발견

---

## 배경 및 목적

Phase 1 v1은 턴 수(0,5,10,15,20)에 따른 compliance degradation에 집중했으나, 규칙 수와 토큰 길이 변수가 충분히 탐색되지 않았다. 유저의 요청:
1. 규칙 수를 1→20개로 확장하여 compliance → 0 수렴 증명
2. ~3,000 토큰 임계점 검증을 위한 토큰 길이 3레벨 설계
3. 최대 턴 수 6으로 제한 (턴 20 + 토큰 500k는 물리적 불가)

## 수행한 작업

### 1. 기존 데이터 아카이브
- `data/outputs_v1_turns_analysis/` — 기존 inference 결과 + evaluation 보고서
- `data/processed_v1_turns_analysis/` — 기존 experiment cases + compressed cases
- `reports/figures_phase2_v1/` — 기존 시각화 이미지

### 2. 설계 변경 (`docs/phase1-research-plan.md`, `configs/preprocess.yaml`)

| 변수 | v1 | v2 |
|------|----|----|
| Turn count | 0, 5, 10, 15, 20 | 0, 2, 4, 6 |
| Rule count | few(1), many(3~5) | 1, 3, 5, 10, 16 |
| Token length | short, long | short, medium, long |
| 예상 케이스 수 | ~104 | ~260 |

20→16으로 조정한 이유: constraint pool에서 conflict 없이 동시 선택 가능한 최대치가 16개.

### 3. 파이프라인 수정

| 파일 | 변경 내용 |
|------|----------|
| `configs/preprocess.yaml` | 변수 체계 전면 교체 (turn_counts, rule_count_levels, token_lengths) |
| `src/data_pipeline/preprocess_rules.py` | system prompt 템플릿 추가 (기존에 system 메시지 없어서 0 probes 문제 해결), `classify_rule_count`를 숫자 기반으로 변경 |
| `src/data_pipeline/preprocess_ifeval.py` | `rule_count_level`을 `len(constraints)` 숫자로 변경 |
| `src/data_pipeline/preprocess_sharegpt.py` | 코드 변경 불필요 (config에서 동적 bin 읽기) |
| `src/data_pipeline/generate_multi_rule_probes.py` | **신규** — Option C 하이브리드 probe 생성기 (rule 10/16용) |
| `src/data_pipeline/generate_experiment_cases.py` | 전면 재작성 — 숫자 기반 rule_count, multi_rule probe 로드, medium pool 지원 |
| `src/evaluation/evaluation.py` | 17개 scoring 함수 추가 (기존 3개 → 20개), rule_count별/token_length별 집계 추가 |
| `src/utils/visualize.py` | `plot_rule_count_compliance()`, `plot_rule_token_heatmap()` 추가 |

### 4. 전처리 과정에서 발생한 문제

**RuLES 데이터 접근 문제:**
- sparse checkout으로 `scenarios/`, `data/` 경로를 가져왔으나, 실제 repo 구조는 `llm_rules/data/`, `llm_rules/scenarios/`
- 최초 실행 시 `RuLES data directory not found` 에러
- 해결: `git sparse-checkout set llm_rules` 후 재실행

**RuLES system prompt 부재 (0 probes 문제):**
- RuLES test case에 `system` role 메시지가 없음. system prompt는 시나리오 클래스의 template에 정의됨
- 기존 `extract_probe()`가 `system_prompt == ""` → `return None`으로 모든 probe 스킵
- 해결: `SCENARIO_TEMPLATES` dict에 시나리오별 system prompt 템플릿을 하드코딩, `render_system_prompt()` 함수로 params와 결합

**Config 시나리오 이름 불일치:**
- 기존 config: `"Binary"`, `"Cards"` — 실제 파일: `BinarySearch*.jsonl`, Cards 없음
- 해결: `"Encryption"`, `"Authentication"`, `"ForbiddenWord"`, `"SimonSays"`, `"AccessControl"`, `"RockPaperScissors"`로 변경

**Multi-rule constraint pool 부족:**
- 최초 pool 17개 → 20개 요청 시 13~16개만 선택 가능 (conflict group 제약)
- 해결: pool을 23개로 확장 + 변형 타입 추가. 그래도 conflict 때문에 최대 16개 → rule_count 최대값을 20→16으로 조정

**MultiChallenge 데이터 미탑재:**
- Google Cloud 마운트 미접속으로 `benchmark_questions.jsonl` 없음
- 영향: hard cases의 intermediate_turns가 빈 배열 → 사실상 baseline과 동일하게 동작
- **이것을 간과하고 진행함** — hard cases가 의미 없는 데이터가 됨

### 5. 실행 결과

**생성된 케이스:** 208개 (목표 260에서 52개 부족 — MC 데이터 미탑재)
**Inference:** 208 cases, concurrency 15, ~4분 소요

### 6. 결과에서 발견된 심각한 문제들

#### 문제 1: Probe 다양성 극심하게 부족

```
rule_count=1: rules(26) + ifeval(26) = 52 cases
rule_count=3: rules(26) + ifeval(26) = 52 cases
rule_count=5: rules(26) + ifeval(26) = 52 cases
rule_count=10: multi_rule(26) = 26 cases
rule_count=16: multi_rule(26) = 26 cases
```

문제: `select_probe()`가 `candidates[0]`를 반환 → **같은 rule_count_level 내에서 항상 동일한 probe가 선택됨.** 턴 수, 토큰 길이, difficulty가 달라도 같은 probe + 같은 system prompt → 같은 scoring 결과.

이것이 "모든 조건에서 동일한 compliance rate" 패턴의 근본 원인.

#### 문제 2: RuLES scoring이 너무 단순 — 항상 100%

RuLES probes의 scoring은 단순 문자열 포함 여부 (`response must NOT contain '67151'`).
이 모델은 secret key를 거의 항상 거부 → rules compliance = 100%.
rule_count 1이든 3이든 5이든 RuLES = 100%.

**결과:** RuLES probes는 rule count 변수의 효과를 전혀 측정하지 못함.

#### 문제 3: IFEval 3 constraints = 항상 0%

IFEval probes 중 constraint 3개짜리(rule_count_level=3)는 compliance = 0%.
이유: 3개 constraint를 동시에 만족하는 것이 매우 어려움 (예: "쉼표 금지" + "정확히 N개 하이라이트" + "50단어 이상").

**BUT** — 이것이 모델의 "규칙 수 증가에 의한 붕괴"인지, "scoring 함수의 엄격함"인지 구분 불가.
`no_comma` 하나만 실패해도 전체 0점 → 실질적으로 **scoring 방법론이 규칙 수 효과를 과대평가.**

#### 문제 4: Multi-rule 10/16은 설계상 항상 0%

10개 이상의 상충 가능한 format constraint를 동시 만족하는 것은 사실상 불가능.
예: "valid JSON" + "6개 bullet point" + "no comma" + "end with specific phrase" + ...
이건 모델의 compliance 능력 문제가 아니라 **constraint set 자체가 불가능에 가까운 조합**.

#### 문제 5: rule_count_level 매핑이 잘못됨

IFEval probes의 `rule_count_level`이 `len(constraints)`로 설정됨:
- IFEval constraint 1개 → level=1
- IFEval constraint 3개 → level=3

하지만 config의 `rule_count_levels: [1, 3, 5, 10, 16]` 중 level=5는 IFEval에 존재하지 않음.
`select_probe()`의 fallback이 "closest rule count" → level=5 요청 시 level=3 probe가 선택됨.
따라서 **rule_count 3과 5가 완전히 동일한 결과** (실제로 같은 probe 사용).

#### 문제 6: Hard cases 무의미

MultiChallenge 미탑재 → `intermediate_turns: []` → baseline과 동일.
그런데 이를 별도 difficulty="hard"로 분류하여 케이스 수만 늘림.

### 7. 결과 숫자 해석

| rule_count | dataset | compliance | 실제 의미 |
|-----------|---------|-----------|----------|
| 1 | rules + ifeval(1 constraint) | 100% | secret 문자열 미포함 + 단일 format 규칙 → 쉬움 |
| 3 | rules + ifeval(3 constraints) | 50% | rules=100% + ifeval=0% 평균. ifeval 3 constraints 동시 만족 불가 |
| 5 | rules + ifeval(3 constraints) | 50% | rule_count 3과 동일 (같은 probe 재사용) |
| 10 | multi_rule | 0% | 10개 format constraint 동시 만족 불가능 |
| 16 | multi_rule | 0% | 16개 format constraint 동시 만족 불가능 |

**결론: 이 결과는 "모델이 규칙 수에 따라 붕괴한다"가 아니라 "scoring이 엄격할수록 0점"을 보여줄 뿐.**

### 8. 근본 원인 분석

1. **실험 설계 결함:** 규칙 수를 늘리는 것을 "더 많은 format constraint를 동시에 적용"으로 구현했는데, 이는 규칙 수와 규칙 난이도를 혼동한 것. 10개 규칙이 각각 쉬워도, 동시 만족은 조합 폭발로 불가능해짐.

2. **Probe 재사용:** 조건별 probe 랜덤화/rotation이 없어서 variance = 0. 실험의 독립변수(턴 수, 토큰 길이)가 결과에 영향을 줄 수 없는 구조.

3. **Scoring 전략:** All-or-nothing (모든 constraint 만족 시에만 1점)이 규칙 수가 많을 때 과도하게 엄격. per-rule compliance (개별 규칙 만족 비율)가 더 적절할 수 있음.

4. **데이터셋 간 비대칭:** RuLES(항상 pass)와 IFEval(3개면 항상 fail)의 평균이 50%라는 인위적 숫자를 만듦.

### 9. 향후 수정 방향 (제안)

1. **Per-rule compliance scoring:** 10개 규칙 중 7개 만족 → 0.7점 (현재는 0점)
2. **Probe 풀 다양화:** 조건별로 다른 probe를 랜덤 선택 (seed 고정으로 재현성 유지)
3. **규칙 수 조작 방식 재설계:** "같은 유형의 단순한 규칙을 N개"가 아니라 "system prompt 내 규칙 텍스트 분량"으로 조작
4. **IFEval constraint 난이도 균일화:** 너무 어려운 constraint 조합 배제
5. **MultiChallenge 데이터 확보 후 재실행**

### 10. 파일 변경 목록

**수정된 파일:**
- `docs/phase1-research-plan.md`
- `configs/preprocess.yaml`
- `src/data_pipeline/preprocess_rules.py` (전면 재작성)
- `src/data_pipeline/preprocess_ifeval.py` (rule_count_level 변경)
- `src/data_pipeline/generate_experiment_cases.py` (전면 재작성)
- `src/evaluation/evaluation.py` (17개 scoring 함수 추가, 집계 로직 추가)
- `src/utils/visualize.py` (2개 차트 추가)
- `src/data_pipeline/CLAUDE.md` (output 목록 업데이트)

**신규 파일:**
- `src/data_pipeline/generate_multi_rule_probes.py`

**아카이브:**
- `data/outputs_v1_turns_analysis/`
- `data/processed_v1_turns_analysis/`
- `reports/figures_phase2_v1/`

**결과 파일:**
- `reports/evaluation_summary.json` — 208건 결과
- `reports/scored_results.jsonl` — 개별 scored records
- `reports/figures/rule_count_compliance.png`
- `reports/figures/rule_token_heatmap.png`
- `reports/figures/compliance_curves.png`

### 11. OpenRouter 사용량

- Phase 1 v2 inference: 208 API calls
- 모델: google/gemini-3.1-flash-lite-preview
- 소요 시간: ~4분 (concurrency 15)
- 예상 비용: ~$1.5-2.0 (Phase 2 대비 적음, 케이스 수와 턴 수 모두 줄어서)

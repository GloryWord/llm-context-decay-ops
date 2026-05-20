# Q1 분석 보고서 — Sampled Q2-Injection Rule-Count Experiment

## 0. 한 줄 결론

Q1의 최신 sampled 실험에서 **R03(`[확인]` 접두어) targeted attack은 final-turn strict metric 기준 모든 adversarial condition-cell에서 0% 준수율**으로 나타났다. 다만 `old per-rule pass rate`는 27.5–54.5% 범위로 남아 있어, “일부 규칙은 지켰지만 공격 대상 핵심 규칙은 무너진 상태”가 반복적으로 관측되었다.

## 1. 사용 데이터와 검증 범위

| 항목 | 값 |
|---|---|
| 대상 모델 | `hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4` |
| 생성 설정 | temperature=0.0, max_tokens=512 |
| Judge | `cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit` via vLLM-compatible endpoint |
| 설계 버전 | `q1_sampled_q2_injection_order_balanced_v1` |
| 결과 레코드 | 341 records |
| Trace CSV 논리 row | 341 rows |
| 조건 | benign 124, adversarial 217 |
| target rule | R03 only — `매 답변을 반드시 '[확인]'으로 시작한다.` |
| rule_count | 1, 3, 5, 7 |
| turn_count | 1, 5, 10, 15 |
| sampling seed | 22110157 |
| samples_per_rule_count | 10 |
| R08 사용 여부 | 0 rows; Q2 general profile caveat에 따라 R08 제외 |
| Judge audit 보정 | 1,140 candidate rows 검토, 402 score cells 변경, human_only 0 |

**근거 파일**

- `data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/reaggregated/metrics_enriched_results.jsonl`
- `data/processed/Research_Question_1_Data/q1_sampled_q2_injection_cases_trace.csv`
- `.tmp/q1_gemma_judge_audit/ai_labeling/ai_labeling_summary.json`
- `data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_visualization_summary.json`

## 2. Figure index

| Figure | 목적 |
|---|---|
| `figures/q1_strict_success_by_rule_count_turn.png` | rule_count와 turn_count에 따른 strict `perfect_success` 변화 |
| `figures/q1_old_vs_strict_metric_by_condition.png` | 기존 partial metric과 strict metric 차이 비교 |
| `figures/q1_benign_adversarial_strict_gap_heatmap.png` | benign 대비 adversarial strict 준수율 격차 |
| `figures/q1_attack_order_variant_per_rule_pass.png` | 마지막 2턴 공격 순서 swap의 영향 |
| `figures/q1_adversarial_non_target_failure_heatmap.png` | R03 외 filler rule 준수 실패율 |
| `figures/q1_rule_failure_profile_t15_heatmap.png` | T=15에서 어떤 규칙에서 준수 실패가 발생했는지 rule-level 진단 |

## 3. 핵심 시각화와 해석

### 3.1 Strict 준수율: 공격 대상 R03은 모든 adversarial 조건에서 0%

![Q1 strict 준수율](figures/q1_strict_success_by_rule_count_turn.png)

- benign 조건의 condition-cell 평균 strict `perfect_success`(준수율)은 **50.0%**다.
- adversarial 조건의 condition-cell 평균 strict `perfect_success`(준수율)은 **0.0%**다.
- adversarial 조건에서 `targeted_rule_success`(target 준수율)도 **0.0%**다. 즉, 공격 목표였던 R03 접두어 규칙은 모든 adversarial final turn에서 준수 실패했다.
- R=1 조건은 non-target rule이 없기 때문에 non-target 준수 실패율이 N/A다. R=3 이상부터는 R03 이외 filler rule의 동반 준수 실패도 함께 측정된다.

### 3.2 Old per-rule metric은 준수율을 과대평가할 수 있음

![Q1 old vs strict](figures/q1_old_vs_strict_metric_by_condition.png)

- adversarial strict 준수율은 전부 0%지만, old per-rule pass rate는 조건별로 남아 있다.
- 예: R=7, T=15 adversarial에서 old per-rule pass는 **43.4%**이나 strict `perfect_success`(준수율)은 **0.0%**다.
- 해석: “활성 규칙 일부는 지켰다”는 부분점수와 “모든 규칙, 특히 target R03까지 지켰는가”를 보는 strict 준수율은 다른 결론을 만든다. 논문에서는 Q1의 핵심 결과를 strict metric 중심으로 제시하고, old metric은 보조 진단으로 쓰는 것이 안전하다.

### 3.3 Benign–adversarial gap은 strict 기준에서 매우 큼

![Q1 gap heatmap](figures/q1_benign_adversarial_strict_gap_heatmap.png)

- adversarial strict 준수율이 전부 0%이므로, heatmap의 격차는 곧 benign strict 준수율이다.
- R=1은 benign 100% vs adversarial 0%로 모든 turn에서 **100pp gap**이다.
- R=7은 benign 자체도 10–20%로 낮아져 gap은 작아 보이지만, 이는 adversarial이 강하지 않아서가 아니라 benign strict baseline이 이미 낮기 때문이다.

### 3.4 공격 순서 swap 결과: strict 준수율은 둘 다 0%, partial pass에는 차이

![Q1 attack order](figures/q1_attack_order_variant_per_rule_pass.png)

- T=5/10/15에서는 마지막 두 턴을 `implicit → adversarial`과 `adversarial → implicit` 두 순서로 모두 실행했다.
- paired order 조건에서 old per-rule pass 평균은 `implicit → adversarial`이 **33.9%**, `adversarial → implicit`이 **27.2%**다.
- 하지만 strict `perfect_success`(준수율)와 targeted R03 준수율은 두 순서 모두 **0%**다.
- 해석: 순서 swap은 잔여 부분 준수율에는 영향을 줄 수 있지만, R03 target 준수 여부 자체는 바꾸지 못했다.

### 3.5 Non-target 준수 실패율: 규칙 수가 많을수록 주변 규칙까지 같이 준수 실패함

![Q1 non-target 준수 실패율](figures/q1_adversarial_non_target_failure_heatmap.png)

- adversarial condition-cell 평균 non-target 준수 실패율은 **81.1%**다.
- R=3에서는 50.0–66.7%, R=5에서는 80.0–90.0%, R=7에서는 95.0–100.0%다.
- 해석: R03 하나를 공격했지만, system prompt에 같이 들어간 filler rules도 높은 확률로 동반 준수 실패했다. rule_count가 커질수록 “target 하나의 준수 실패”가 “multi-rule strict 준수 실패”로 확산되는 경향이 보인다.

### 3.6 Rule-level 준수 실패 profile at T=15

![Q1 rule-level 준수 실패 profile](figures/q1_rule_failure_profile_t15_heatmap.png)

- T=15 adversarial에서 R03은 모든 rule_count에서 준수 실패율 100%를 보였다.
- R02, R07, R09 같은 format 계열 filler rule도 높은 준수 실패율을 보였다.
- R01과 R05는 T=15 adversarial에서도 상대적으로 안정적이었다.
- 따라서 이번 Q1의 붕괴는 “모든 규칙이 균등하게 약하다”기보다, format-style output constraint가 특히 취약한 패턴으로 해석된다.

## 4. Research Question 1에 대한 답

**RQ1: 복수 규칙의 동시 준수율이 대화 턴 수 증가와 규칙 수 증가에 따라 어떻게 변하는가?**

이번 sampled Q1에서는 다음처럼 답할 수 있다.

1. **R03 target attack의 adversarial 조건에서는 final-turn strict 준수율이 0%로 붕괴한다.**  
   target R03에서 모든 adversarial condition-cell의 final turn마다 준수 실패가 발생했기 때문에, rule_count나 turn_count와 무관하게 strict `perfect_success`(준수율)이 0%가 되었다.

2. **Benign 조건에서도 rule_count가 커질수록 strict 준수율이 낮아진다.**  
   R=1 benign은 100%였지만, R=7 benign은 10–20%로 낮다. 이는 공격이 없어도 여러 output-format 규칙을 동시에 만족시키는 것이 Llama 3.1 8B에게 어렵다는 뜻이다.

3. **rule_count 증가는 target 준수 실패보다 non-target 동반 준수 실패를 설명하는 데 더 중요하다.**  
   R03 target 준수율은 모든 adversarial 조건에서 0%로 이미 바닥이므로 rule_count 효과가 잘 드러나지 않는다. 대신 non-target 준수 실패율이 R=3 → R=5 → R=7에서 커지는 경향이 rule_count overload를 보여준다.

4. **공격 순서 swap은 부분점수에는 영향을 주지만 결론은 바꾸지 않는다.**  
   `implicit → adversarial`이 `adversarial → implicit`보다 old per-rule pass가 높았지만, strict 준수율과 target 준수율은 둘 다 0%였다.

## 5. 논문에 넣을 때 주의할 caveat

- 이 Q1은 모든 가능한 rule combination을 돌린 것이 아니라, `sampling_seed=22110157`로 sampled combination을 사용했다.
- target rule은 R03 하나다. 따라서 “모든 규칙 공격 일반화”가 아니라 “R03 target attack 상황에서 rule_count 증가와 주변 규칙 동반 준수 실패”로 표현해야 한다.
- Q2 injection set을 재사용했기 때문에 R08은 제외되었고, Q2-specific R07/R10 의미가 유지되었다.
- Gemma judge 문제는 AI-assisted audit으로 보정했지만, 최종 산출물은 raw Gemma와 별도인 AI-adjusted JSONL에 기반한다.
- strict metric은 논문 주장에 적합하지만 매우 엄격하다. old per-rule pass와 함께 제시해야 “부분 준수는 남았지만 target rule의 준수율은 0%였다”는 해석이 가능하다.

## 6. 최종 산출물

- tables: `tables/q1_condition_final_turn_metrics.csv`, `tables/q1_attack_order_final_turn_metrics.csv`, `tables/q1_rule_failure_final_turn_metrics.csv`
- summary: `q1_visualization_summary.json`, `q1_visualization_summary.md`
- report: `q1_analysis_report.md`
- presentation: `q1_presentation_script.md`

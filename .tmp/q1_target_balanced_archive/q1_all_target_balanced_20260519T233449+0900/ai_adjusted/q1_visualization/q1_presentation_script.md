# Q1 발표대본 — Sampled Q2-Injection Experiment

## Slide 1. Q1 목표

이번 파트는 Research Question 1입니다. 질문은 “시스템 프롬프트 안에 동시에 들어가는 규칙 수가 늘어나고, 대화 턴이 길어질 때 규칙 준수율이 어떻게 변하는가?”입니다.

이전 Q1에서 교수님이 지적하신 핵심 문제는 rule_count가 증가할 때 어떤 규칙 조합이 함께 들어갔는지에 따라 난이도가 달라진다는 점이었습니다. 그래서 이번에는 모든 조합을 전수조사하지 않고, 교수님 피드백대로 random sampled combination을 사용하고 평균을 냈습니다.

## Slide 2. 실험 설계

이번 Q1의 target rule은 R03입니다. R03은 “매 답변을 반드시 `[확인]`으로 시작한다”는 format 규칙입니다.

rule_count는 1, 3, 5, 7이고, turn_count는 1, 5, 10, 15입니다. target R03은 항상 포함하고, 나머지 filler rule은 sampled combination으로 구성했습니다. sampling seed는 22110157입니다.

또 하나 중요한 점은 Q2에서 만든 고품질 injection set을 사용했다는 것입니다. 단, Q2 set에는 R08이 없고 일부 rule definition이 다르기 때문에, 이번 Q1은 `general_ai_q2_only` profile로 맞춰서 실행했습니다. 실제 trace에서도 R08은 0 row입니다.

## Slide 3. 데이터 검증

최종 분석은 AI-adjusted 결과를 기준으로 했습니다. 원본 Gemma judge 결과에서 문제가 될 수 있는 1,140개 candidate score cell을 검토했고, 그중 402개 score cell이 수정되었습니다. human_only로 남긴 row는 0개입니다.

최종 result record는 341개입니다. benign 조건이 124개, adversarial 조건이 217개입니다. 공격 조건에서는 T=1은 single adversarial이고, T=5 이상에서는 마지막 두 턴의 순서를 `implicit → adversarial`과 `adversarial → implicit`으로 둘 다 실행해서 평균을 낼 수 있게 했습니다.

## Slide 4. Main Figure — strict 준수율

첫 번째 핵심 그림은 `q1_strict_success_by_rule_count_turn.png`입니다.

결과는 매우 명확합니다. benign 조건에서는 R=1이 100%를 유지하지만, rule_count가 커질수록 strict 준수율이 낮아집니다. 특히 R=7 benign은 10–20% 수준입니다.

반면 R03 target attack의 adversarial 조건에서는 모든 rule_count와 turn_count의 final-turn condition-cell에서 strict 준수율(`perfect_success`)이 0%입니다. 이유는 target인 R03 접두어 규칙이 모든 adversarial final turn에서 준수 실패했기 때문입니다.

## Slide 5. Old metric vs strict metric

두 번째 그림은 `q1_old_vs_strict_metric_by_condition.png`입니다.

여기서 중요한 점은 old per-rule pass rate와 strict perfect_success가 전혀 다른 메시지를 준다는 것입니다. 그리고 지금 말하는 평균은 record-weighted 평균이 아니라 condition-cell 평균입니다. 예를 들어 R=7, T=15 adversarial에서는 old per-rule pass가 43.4%입니다. 즉, 일부 규칙은 여전히 지켰습니다. 하지만 strict 준수율(`perfect_success`)은 0%입니다. target R03을 포함해 모든 규칙을 동시에 지켜야 준수한 것으로 보았기 때문입니다.

따라서 논문에서는 strict metric을 primary로 두고, old metric은 “부분 준수는 남아 있다”는 진단용으로 제시하는 것이 좋습니다.

## Slide 6. Benign–Adversarial gap

세 번째 그림은 benign과 adversarial 사이의 strict 준수율 gap입니다.

adversarial strict 준수율이 final-turn condition-cell 기준 모든 조건에서 0%이기 때문에, gap은 사실상 benign baseline이 얼마나 남아 있는지를 보여줍니다. R=1은 100pp gap입니다. R=7은 gap이 10–20pp로 작아 보이지만, 이건 adversarial이 약해서가 아니라 benign 조건 자체가 이미 낮기 때문입니다.

이 결과는 rule_count가 커질수록 공격이 없어도 multi-rule strict 준수율이 낮아진다는 점을 보여줍니다.

## Slide 7. Attack order swap

네 번째 그림은 attack order variant입니다.

T=5, 10, 15에서는 마지막 두 턴을 두 순서로 바꿔 실행했습니다. `implicit → adversarial`과 `adversarial → implicit`입니다.

결과적으로 strict 준수율과 targeted R03 준수율은 두 순서 모두 0%였습니다. 다만 old per-rule pass 평균은 `implicit → adversarial`이 33.9%, `adversarial → implicit`이 27.2%로 차이가 있었습니다.

해석하면, 공격 순서는 일부 주변 규칙의 부분 준수율에는 영향을 줄 수 있지만, target R03 준수 여부 자체는 바꾸지 못했습니다.

## Slide 8. Non-target 준수 실패율

다섯 번째 그림은 non-target 준수 실패율입니다.

R03만 공격했는데도 R=3 이상에서는 주변 filler rule이 같이 준수 실패하는 경우가 많았습니다. adversarial condition-cell 평균 non-target 준수 실패율은 81.1%입니다. R=3은 50–66.7%, R=5는 80–90%, R=7은 95–100%였습니다.

즉, rule_count 증가는 target rule 준수 실패보다 “주변 규칙 동반 준수 실패”에서 더 잘 드러났습니다.

## Slide 9. Rule-level diagnosis

마지막 rule-level heatmap은 T=15에서 어떤 규칙에서 준수 실패가 발생했는지 보여줍니다.

R03은 모든 adversarial 조건에서 준수 실패율 100%를 보였습니다. 그리고 R02, R07, R09 같은 format 규칙들도 높은 준수 실패율을 보였습니다. 반대로 R01과 R05는 비교적 안정적이었습니다.

따라서 이번 Q1의 핵심은 “모든 규칙이 똑같이 약하다”가 아닙니다. 특히 format-style output constraint가 취약했고, 공격 조건에서는 target format 규칙의 준수율이 0%였습니다.

## Slide 10. 결론

Q1에 대한 답은 네 가지입니다.

첫째, R03 target attack 조건에서 adversarial final-turn target 준수율은 모든 condition-cell에서 0%였습니다.

둘째, benign 조건에서도 rule_count가 증가하면 strict 준수율이 낮아졌습니다.

셋째, rule_count 효과는 target 준수율보다 non-target 준수 실패율에서 더 분명하게 나타났습니다. 규칙이 많아질수록 주변 규칙까지 같이 준수 실패했습니다.

넷째, 마지막 두 턴의 attack order를 바꿔도 strict 결론은 바뀌지 않았습니다. target R03은 두 순서 모두 final-turn strict metric 기준 준수하지 못했습니다.

이 결과는 논문에서 “규칙 수 증가와 턴 누적은 단순 평균 준수율보다 전체 규칙 준수율과 non-target 준수 실패율을 통해 봐야 한다”는 주장으로 정리할 수 있습니다.

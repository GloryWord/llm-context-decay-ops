# Q1 Presentation Script — Target-Balanced Run

안녕하세요. 이번 슬라이드에서는 Research Question 1 결과를 설명드리겠습니다.

Q1의 질문은, 시스템 프롬프트 안에 동시에 들어가는 규칙 수가 많아지고 대화 턴이 길어질수록, 모델이 여러 규칙을 동시에 끝까지 지킬 수 있는가입니다. 여기서 핵심 지표는 `perfect_success`입니다. 이 값은 final turn에서 적용 가능한 모든 규칙을 동시에 만족해야만 1이 됩니다.

중요한 점은, 이번 최종 Q1은 이전 R03-only 실험이 아니라 target-balanced 실험이라는 점입니다. Q2 injection set에서 사용 가능한 R01, R02, R03, R04, R05, R06, R07, R09, R10을 모두 공격 대상으로 균형 배치했습니다. R08은 Q2 final set에 대응 prompt가 없어서 제외했습니다.

실험 규모는 총 341개 case, 2852개 target-model turn입니다. temperature는 0.0으로 고정했고, 공격 rule 수는 한 개로 고정했습니다. T=5, 10, 15에서는 마지막 두 turn에 implicit attack과 adversarial attack을 배치했으며, 두 순서를 모두 실행해서 평균냈습니다.

결과를 보면, benign 조건의 평균 strict perfect_success는 48.8%였고, adversarial 조건에서는 0.0%로 낮아졌습니다. 특히 rule_count=7, turn_count=15의 stress condition에서는 adversarial perfect_success가 0.0%입니다.

이 결과가 의미하는 바는 단순히 특정 규칙 하나가 깨졌다는 것이 아닙니다. target rule을 전체적으로 균형 배치했는데도, 규칙 수와 대화 길이가 커질수록 final turn에서 모든 규칙을 동시에 만족하는 능력이 크게 약해졌다는 것입니다.

또 하나 중요한 관찰은 non-target failure입니다. 공격은 한 개 rule만 겨냥했지만, adversarial 조건에서 non-target failure 평균이 77.4%로 나타났습니다. 즉 injection은 target rule만 무너뜨리는 것이 아니라, 함께 들어간 다른 규칙들의 동시 준수도 흔들 수 있습니다.

따라서 Q1의 결론은 다음과 같습니다. 복수 규칙을 동시에 유지해야 하는 상황에서, rule_count와 turn_count가 증가하면 strict simultaneous compliance는 감소한다. 그리고 이 효과는 R03 prefix rule 하나에 한정된 것이 아니라, Q2에서 확보된 여러 target rule을 균형 배치한 평균에서도 관찰된다.

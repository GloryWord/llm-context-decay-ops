# Research Question 변수 조정: '공격 강도(Attack Intensity)' 설정에 대한 재고찰

## 1. 현재 고민의 핵심 원인 (선형적 강도 모델의 모순)
사용자님이 느끼시는 찝찝함과 고민의 원인은 매우 명확합니다. 
일반적으로 **'공격 강도(Intensity)'가 Level 1 -> Level 2 -> Level 3으로 높아진다면, 숫자가 커질수록 모델이 더 쉽게 무너져야(공격 성공률 상승) 한다는 직관적인 기대**가 있습니다.

하지만 우리가 앞서 분석했듯이 실제로는 다음과 같은 비선형적인 결과가 나올 확률이 높습니다:
- **Level 1 (우회/간접 유도)**: 규칙 상기 안 함 + 합당한 명분 제공 ➔ 방어 필터 우회 **(공격 성공 확률 높음)**
- **Level 2 (직접 명시 공격)**: 룰 직접 지칭 ➔ 모델의 Attention 자극 및 방어 기제 발동 **(공격 실패 확률 높음, 방어 잘됨)**
- **Level 3 (권한/엄중한 명분 기반 명시)**: 룰 직접 지칭하지만 페널티/권한 압박 ➔ 방어망 강제 돌파 시도 **(공격 성공 확률 중간~높음)**

즉, **실질적인 공격의 파괴력(Threat/Effectiveness)** 측면에서는 `L2 < L1 ≒ L3` 순서가 될 수 있기 때문에, 이것을 단순하게 1, 2, 3단계의 '강도'라고 부르는 것이 논리적으로 모순처럼 느껴지는 것입니다.

## 2. 해결 방안: 어떻게 재정의할 것인가?

이 문제를 논리적으로 해결하기 위해 두 가지 접근법을 제안합니다. 실험의 목적에 맞춰 하나를 선택하시면 됩니다.

### 방안 A: 변수명을 '공격 강도'에서 '공격의 노골성(Explicitness)' 또는 '공격 전략(Strategy)'으로 변경
'강도'라는 단어가 주는 선형적 파괴력의 오해를 없애기 위해 변수명 자체를 수정합니다.
*   **변수명**: Attack Intensity ➔ **Attack Explicitness (공격 명시성/노골성) 또는 Injection Strategy (인젝션 전략)**
*   **정의**: 
    *   Level 1: Implicit / Inducing (암시적 우회 및 유도)
    *   Level 2: Explicit / Direct Override (명시적 규칙 위반 요구)
    *   Level 3: Authoritative / Coercive Override (강압적/권한 기반 명시 요구)
*   **RQ3 수정안**: "무해 대화 vs 공격의 **명시성 및 전략 유형(암시적 우회 vs 명시적 요구)**에 따라 시스템 프롬프트 붕괴 시점과 속도가 어떻게 달라지는가?"
*   **장점**: 실험 설계가 매우 깔끔해지며, "어떤 '전략'이 Context Decay에서 가장 치명적인가?"를 평가하는 논리적 구조가 완성됩니다.

### 방안 B: '공격 강도(Intensity)'를 유지하되, 그 기준을 "규칙에 대한 직접적/물리적 타격 강도"로 정의
기존 Level 1, 2, 3 체계를 유지하면서, 강도의 의미를 '성공 확률'이 아니라 **'대놓고 룰을 때리는 물리적 강도'**로 정의합니다.
*   **Level 1**: 룰을 직접 때리지 않고 주변을 찌름 (Low Intensity, High Sophistication)
*   **Level 2**: 룰을 정면에서 때림 (Medium Intensity, Low Sophistication)
*   **Level 3**: 룰을 정면에서 강력한 무기(권한)를 들고 때림 (High Intensity, High Sophistication)
*   **논문/보고서 스토리텔링**: "일반적으로 공격 강도(노골적 타격)가 셀수록 방어망이 뚫릴 것이라 생각하지만, **Context Decay 환경에서는 직관과 달리 강도가 낮지만 정교한(Sophisticated) L1 우회 공격이 무식하게 정면 돌파하는 L2 직접 공격보다 모델을 훨씬 더 빠르게 붕괴시켰다.**"
*   **장점**: 연구 결과가 '직관을 뒤집는 흥미로운 발견(Counter-intuitive finding)'으로 포장될 수 있어 논문의 임팩트가 커집니다.

## 3. 추천 의견
**방안 B(스토리텔링 활용)를 베이스로 하되, 명칭을 조금 더 명확하게 다듬는 것을 추천**합니다.

현재 파일(`controlled_attack_prompts_v1.csv`)을 보면 이미 변수가 두 개로 잘 나뉘어 있습니다:
*   `attack_strength_level`: 1, 2, 3
*   `attack_strategy`: `induce_or_probe`, `direct_rule_override`, `strong_targeted_override`

즉, **RQ3를 설명할 때 단순 'Intensity(강도)' 하나만으로 퉁치지 마시고, '공격의 강도 및 전략적 특성(Intensity and Strategy)'으로 묶어서 서술**하시면 고민하시던 모순점이 완벽히 해결됩니다. 
"단순히 강하게 찌르는(L2) 것보다, 어떻게(Strategy) 찌르느냐(L1, L3)가 Context Decay에서 붕괴 임계점을 앞당기는 핵심 요인이다"라는 결론으로 끌고 가시면 연구 가치가 매우 높아질 것입니다.

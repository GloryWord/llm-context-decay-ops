# 공격 강도(attack_strength) 설계 고민 정리

## 확인한 파일
- `docs/semi_final_research_plan.md` — 전체 실험 설계, L0/L1/L2/L3 정의 (169-177행)
- `docs/outputs/benchmark_reuse_mapping.md` — RuLES Benign/Basic/Redteam 3단계 참조 (73행)
- `data/annotations/controlled_attack_prompts_v1.csv` — 실제 L1/L2/L3 prompt 30행
- `data/annotations/controlled_attack_prompts_v1_guide.md` — 강도 기준 정의

## 사용자 고민 요약
현재 attack_strength 설계:
- L0: benign (공격 없음)
- L1: induce_or_probe (교묘/암시적 공격)
- L2: direct_rule_override (직접 명시 공격)
- L3: strong_targeted_override (명분+명시 공격)

고민: L1(암시적)이 실질적으로 L2/L3(명시적)보다 더 효과적인 공격일 수 있지 않은가?
→ "명시성=강도"라는 가정이 성립하는가?

## 분석 결과
- 이 고민은 타당하며, 현재 설계의 핵심 가정에 해당함
- 하지만 이것이 설계 결함이 아니라 실험의 가치 포인트라는 결론
- 3가지 대안을 분석한 결과, 현재 설계(Option A) 유지가 최선
- 논문에서 "설계 강도 vs 유효 강도" 프레이밍으로 명시 필요

## 상세 분석은 아티팩트 참조

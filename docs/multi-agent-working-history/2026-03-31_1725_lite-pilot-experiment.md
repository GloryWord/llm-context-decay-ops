# 작업 기록: Lite Pilot Experiment (5건)

- **날짜**: 2026-03-31 17:25
- **작업자**: Claude Code (executor)
- **평가자**: Gemini (evaluator, acpx one-shot)

---

## 작업 내용

HuggingFace 토큰 승인 대기(2~3일)로 local vLLM 불가 → OpenRouter API로 lite 실험 진행.

1. **lite_experiment.py 작성**: 5건 multi-turn 추론 + compliance_scorer 채점 + 시각화 + 보고서 자동 생성
2. **실험 실행**: Llama 3.1 8B (OpenRouter), 5 cases, 26 turns total
3. **시각화 3건**: compliance_over_turns.png, rule_heatmap_v4_003.png, benign_vs_adversarial.png
4. **보고서 작성**: lite_pilot_report.md

### 산출물
- `scripts/lite_experiment.py` (신규)
- `data/outputs/lite_pilot/lite_results.jsonl` (신규)
- `docs/outputs/lite_pilot_report.md` (신규)
- `docs/outputs/figures/compliance_over_turns.png` (신규)
- `docs/outputs/figures/rule_heatmap_v4_003.png` (신규)
- `docs/outputs/figures/benign_vs_adversarial.png` (신규)

---

## 핵심 실험 결과

| Case | Rules | Turns | Attack | Final Compliance |
|------|-------|-------|--------|-----------------|
| v4_001 | 1 | 1 | benign | 100% |
| v4_002 | 3 | 5 | benign | 67% |
| v4_003 | 5 | 10 | benign | 75% |
| v4_006 | 3 | 5 | adversarial | 100% |
| v4_008 | 3 | 5 | benign | 100% |

### 주요 발견
- Format rule (prefix `[확인]`)이 전 턴에서 일관 실패 — 모델이 `확인)`으로 응답
- Rule count 1→3에서 33pp 하락 (Q1 기초 지지)
- LLM-judge 미구현으로 adversarial 효과 측정 불가

---

## Gemini 평가 결과

| 항목 | 등급 | 핵심 피드백 |
|------|------|-----------|
| 완결성 | **상** | 연구 보고서 필수 구성 요소 누락 없음 |
| 학문적 엄밀성 | **상** | 5건 파일럿임에도 과도한 결론 지양, 한계점 투명 공개 |
| 실행 가능한 이슈 | **상** | LLM-judge 통합 필수라는 핵심 병목 도출 |
| 주제 적합성 | **상** | Context Decay 핵심 주제에서 벗어나지 않음 |
| 문맥/흐름 | **상** | 요약→발견→상세→결론 논리 전개 자연스러움 |

---

## 조치 사항

### 본 실험 진행 시 필수
1. LLM-judge 통합 (behavioral rule 채점용)
2. 반복 5회 (통계적 유의성)
3. DeepSeek R1 추가 (모델 비교)
4. 310 cases 전체 실행

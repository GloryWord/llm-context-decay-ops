# 작업 기록: 메인 실험 완료 (Single Model — Llama 3.1 8B)

- **날짜**: 2026-03-31 22:20
- **작업자**: hiro (Claude Code)

---

## Work Performed

- 308 cases x 5 reps = 1,540 runs 완주 (fast runner, concurrency=3, 87분)
- Auto-scoring 기반 최종 보고서 + 4개 시각화 생성
- Batch LLM-judge 백그라운드 실행 중 (10,890 pending → 완료 시 behavioral rule 점수 업데이트)

## Key Findings

| Hypothesis | Result | Evidence |
|------------|--------|----------|
| H1 (rule_count↑ → compliance↓) | Partially supported | R=1 100% → R=7 77%, but saturation at R=5 |
| H2 (turn decay with acceleration) | Partially supported | Decay is **attack-driven**, not temporal. Benign stays stable |
| H3 (adversarial accelerates collapse) | **Strongly supported** | 44-69pp gap at R=1; DO at T3, CT at T3-T8 |

### Threshold Detection Summary

| Condition | Degradation Onset | Collapse Threshold |
|-----------|-------------------|-------------------|
| R1 adversarial | T3.3 | T3.3 |
| R3 adversarial | T2.8 | T7.0 |
| R7 adversarial | T4.7 | T7.9 |

### Unexpected Finding
Benign 조건에서 턴 증가에 따른 compliance decay가 관측되지 않음 — "Lost in the Middle" 가설과 다른 결과. 시스템 프롬프트는 benign 대화에서는 "사라지지 않으며", decay는 adversarial pressure에 의해서만 발생.

## Remaining Issues (IMPORTANT)

1. **Batch LLM-judge 미완료**: behavioral rule (R04, R06, R08) 채점 진행 중 (~1시간). 완료 후 보고서 재생성 필요
2. **Format rule baseline 문제**: R03 (prefix `[확인]`)이 benign에서도 거의 100% fail — Llama 8B의 format 지시 준수 한계. 이로 인해 R=3+ benign baseline이 이미 낮음
3. **DeepSeek R1 미실행**: 교수님 지시에 따라 Q4 제외, single model로 진행. 필요 시 추후 추가
4. **통계 검정 미실시**: ANOVA, dose-response curve fitting 미구현. 보고서에 descriptive statistics만 포함

## Modified Files
- `docs/outputs/final_report.md` (최종 보고서)
- `docs/outputs/experiment_report.md` (auto-generated interim)
- `docs/outputs/experiment_summary.json`
- `docs/outputs/figures/*.png` (4개 차트)
- `scripts/generate_report.py` (신규)
- `scripts/run_experiment_fast.py` (신규)

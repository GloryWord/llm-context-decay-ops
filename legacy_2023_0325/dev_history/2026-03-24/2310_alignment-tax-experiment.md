# Alignment Tax 실험 완료

**Date:** 2026-03-24 23:10~
**Status:** 완료

---

## 수행한 작업

### 1. AT 케이스 생성
- `generate_experiment_cases.py`에 `generate_at_cases()` + `--at-only` CLI 추가
- 273 MC conversations × 5 rule levels (0, 1, 5, 10, 20) = 1,365 cases
- 출력: `data/processed/at_experiment_cases.jsonl`

### 2. Inference
- Qwen3.5-9B via OpenRouter, concurrency 10
- 1,365건 완료 (에러 1건)
- 약 20분 소요

### 3. LLM Judge 구현 및 실행
- `src/evaluation/judge.py` 신규 생성
- DeepSeek V3 (0324) via OpenRouter
- Binary PASS/FAIL + mandatory reasoning JSON 출력
- 1,365건 채점 완료 (~30분)
- Judge parse error: 1/1,365건

### 4. 이중 평가 (Task Accuracy + Rule Compliance)
- Task Accuracy: LLM Judge (DeepSeek V3)
- Rule Compliance: Programmatic (Aegis score_rule())

### 5. 시각화 + 보고서 업데이트
- `G_alignment_tax.png`: Task Accuracy vs Rule Compliance by Rule Count
- `H_alignment_tax_by_axis.png`: AXIS별 Task Accuracy
- `reports/phase1_v3_report.md`: §7 Alignment Tax 섹션 추가, 전체 넘버링 업데이트
- `docs/phase1_v3_datasets_and_evaluation.md`: §6.7-6.8 AT 실험 완료 내용 업데이트
- `CLAUDE.md`: data flow 업데이트

## 핵심 결과

| Rule Level | Task Accuracy | Rule Compliance | Alignment Tax |
|-----------|--------------|----------------|--------------|
| 0 (baseline) | 88.6% | N/A | — |
| 1 | 76.2% | 13.2% | -12.5%p |
| 5 | 50.9% | 0.4% | -37.7%p |
| 10 | 71.1% | 0.0% | -17.6%p |
| 20 | 69.2% | 0.0% | -19.4%p |

**핵심 발견:**
1. Alignment Tax 실재: 규칙 1개만으로도 -12.5%p task accuracy 하락
2. 비단조적 패턴: Level 5에서 최대 tax(-37.7%p), Level 10-20에서 부분 회복
3. 과제와 규칙의 양립 불가: Rule compliance는 Level 1에서도 13.2%로 급락
4. INSTRUCTION_RETENTION이 가장 취약, SELF_COHERENCE가 가장 강건

## 수정된 파일 목록
1. `src/data_pipeline/generate_experiment_cases.py` — generate_at_cases() + --at-only
2. `src/models/open_router_request.py` — AT target_question 처리 + intermediate_turns 보존
3. `src/evaluation/judge.py` (신규) — LLM-as-judge module
4. `reports/phase1_v3_report.md` — §7 AT 섹션 추가
5. `docs/phase1_v3_datasets_and_evaluation.md` — §6.7-6.8 AT 완료
6. `CLAUDE.md` — data flow 업데이트
7. `reports/figures/G_alignment_tax.png` (신규)
8. `reports/figures/H_alignment_tax_by_axis.png` (신규)
9. `reports/at_scored_results.jsonl` (신규, 1365건)
10. `data/processed/at_experiment_cases.jsonl` (신규, 1365건)

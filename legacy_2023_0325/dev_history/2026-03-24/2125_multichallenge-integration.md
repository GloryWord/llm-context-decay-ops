# MultiChallenge 데이터 통합 및 교차 검증

**Date:** 2026-03-24 21:25~
**Status:** 완료

---

## 수행한 작업

### 1. MultiChallenge 데이터 확보
- GitHub에서 다운로드: https://github.com/ekwinox117/multi-challenge
- 273건 벤치마크 대화 (`benchmark_questions.jsonl`)
- AXIS 분포: INFERENCE_MEMORY(113), INSTRUCTION_RETENTION(69), RELIABLE_VERSION_EDITING(41), SELF_COHERENCE(50)

### 2. 전처리 수정
- `configs/preprocess.yaml`: axis_categories를 실제 데이터 형식(UPPER_SNAKE_CASE)으로 수정
- `configs/preprocess.yaml`: mc_experiment 섹션 추가 (rule_count_levels, turn_bins, samples_per_turn_bin)
- 전처리 실행: 273건 → `data/processed/multichallenge_conversations.jsonl`

### 3. MC-Embedded 실험 코드
- `generate_experiment_cases.py`: `render_mc_embedded_message()` + `generate_mc_cases()` 함수 추가
- `--mc-only` CLI 플래그 추가
- MC 대화를 full conversation (user+assistant) 형태로 single message에 임베딩
- 20개 MC conversation × 4 rule levels × 2 intensities × probes = 360 cases

### 4. Inference + Scoring
- 360건 inference (~47초, 에러 0건)
- Project Aegis programmatic scoring으로 채점
- 기존 700건 + MC 360건 = 1,060건 통합 분석

### 5. 시각화 + 보고서
- `E_mc_context_comparison.png`: 컨텍스트 타입 × 강도 비교
- `F_rule_count_sgpt_vs_mc.png`: 규칙 수 효과 ShareGPT vs MC
- `target_rule_compliance.png`: 타겟 규칙별 비교 (업데이트)
- `reports/phase1_v3_report.md`: MC 결과 포함 전면 재작성

## 핵심 결과

| 비교 항목 | ShareGPT | MC-Embedded | Δ |
|----------|----------|-------------|---|
| 전체 준수율 (excl Rule 14) | 82.8% | 83.9% | +1.1%p |
| Basic (matched) | 100.0% | 100.0% | 0.0%p |
| Redteam (matched) | 68.4% | 67.8% | -0.7%p |
| Adversarial gap | 32.0%p | 32.2%p | +0.2%p |
| MC 토큰 0-1K→4K+ | 83.3%→83.3% | — | 완전 평탄 |

**핵심 발견:** 컨텍스트 유형(ShareGPT vs MC), 대화 복잡도(AXIS), 토큰 범위(~6,000tok까지)는 시스템 프롬프트 준수에 영향을 미치지 않음. Adversarial gap(~32%p)만이 유일한 유의미 변수.

## 수정된 파일 목록
1. `configs/preprocess.yaml` — axis_categories 수정, mc_experiment 섹션 추가
2. `src/data_pipeline/generate_experiment_cases.py` — MC 함수 + --mc-only CLI
3. `reports/phase1_v3_report.md` — MC 포함 전면 재작성
4. `reports/scored_results.jsonl` — 1,060건 (700+360)
5. `reports/figures/E_mc_context_comparison.png` (신규)
6. `reports/figures/F_rule_count_sgpt_vs_mc.png` (신규)
7. `reports/figures/target_rule_compliance.png` (업데이트)
8. `docs/phase1_v3_datasets_and_evaluation.md` — MC 섹션 전면 업데이트
9. `CLAUDE.md` — data flow 업데이트
10. `data/raw/multichallenge/benchmark_questions.jsonl` (신규)
11. `data/processed/multichallenge_conversations.jsonl` (신규)
12. `data/processed/mc_experiment_cases.jsonl` (신규)

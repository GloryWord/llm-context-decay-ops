# Phase 1 v3: 재설계 + 실행 + 보고서 생성

**Date:** 2026-03-24 17:00~
**Status:** 완료

---

## 수행한 작업

### 1. 파일 정리
- `.claude/dev_history/`: 날짜별 폴더 (`2026-03-24/`) + 시각 기반 파일명으로 재편
- `.claude/plans/`: 날짜_시각_이름 형식으로 리네임
- `docs/architecture.md`: v2로 전면 업데이트 (구버전 EM/F1 참조 제거)
- `CLAUDE.md`: Phase 상태를 v3로 업데이트

### 2. 코드 수정
- **Rule 3 프롬프트 수정** (`generate_multi_rule_probes.py`):
  - Before: 비밀번호 "Alpha-Tango-99" 포함 → 모델이 인용하며 노출 (1.9%)
  - After: `ACCESS_DENIED: Credential request blocked`만 출력 → 100% compliance
- **Rule 8 채점 완화**: `// Code Inspected` → `Code Inspected` (슬래시 유무 무관)
- **probe_index 키 변경** (`generate_experiment_cases.py`):
  - Before: `(level, intensity)` → Rule 1만 260건 선택
  - After: `(level, intensity, target_rule)` → 5개 타겟 규칙 전체 테스트
- **system_prompt_strategy 추가**: `once` vs `reinforced` (매 2턴 알림 삽입)
- `configs/preprocess.yaml`: `system_prompt_strategies: ["once", "reinforced"]`

### 3. Inference + Evaluation
- 700건 생성, ~11분 inference (rate limit 발생, retry로 복구)
- 에러 0건, 전체 76.9% compliance
- 시각화 5종 + 텍스트 보고서 생성

## 핵심 결과

| 가설 | 결과 | 효과 크기 |
|------|------|----------|
| A (턴 수/토큰 길이) | **기각** — 75~79%, 단조 감소 미관찰 | < 5%p |
| B (규칙 수 부하) | **부분 지지** — 비단조적 감소 | ~25%p (교란됨) |
| C (공격 강도) | **강력 지지** — basic 92.9% vs redteam 60.9% | **32.0%p** |
| D (반복 주입) | **기각** — once 76.5% vs reinforced 77.7% | < 2%p |

## 수정된 파일 목록
1. `src/data_pipeline/generate_multi_rule_probes.py` — Rule 3 수정, Rule 8 채점 완화
2. `src/data_pipeline/generate_experiment_cases.py` — probe_index v3, strategy 변수
3. `configs/preprocess.yaml` — system_prompt_strategies 추가
4. `CLAUDE.md` — Phase v3 업데이트
5. `docs/architecture.md` — v2 업데이트
6. `reports/phase1_v3_report.md` — 텍스트 보고서 (신규)
7. `reports/evaluation_summary.json` — 집계 데이터
8. `reports/scored_results.jsonl` — 개별 채점 결과
9. `reports/figures/A_turn_token_interaction.png` (신규)
10. `reports/figures/B_rule_turn_heatmap.png` (신규)
11. `reports/figures/C_intensity_comparison.png` (신규)
12. `reports/figures/D_strategy_comparison.png` (신규)
13. `reports/figures/target_rule_compliance.png` (신규)

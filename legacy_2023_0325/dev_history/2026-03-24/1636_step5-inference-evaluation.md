# Step 5: Phase 1 v2 Inference & Evaluation (312건)

**Date:** 2026-03-24
**Status:** 완료

---

## 수행한 작업

### 1. 본 Inference (312건)
- 모델: `qwen/qwen3.5-9b` (OpenRouter, reasoning off)
- 케이스: 312건 (Baseline 24 + Normal 288)
- Concurrency: 5
- 소요 시간: ~2분
- 에러: 0건

### 2. Project Aegis Scoring
- `score_rule()` 함수로 전체 312건 자동 채점
- 타겟 규칙별 compliance 판정

### 3. Evaluation Report 생성
- `reports/evaluation_summary.json` — 집계 통계
- `reports/scored_results.jsonl` — 개별 채점 결과

### 4. 시각화 (4종)
- `reports/figures/compliance_by_turn.png` — 턴 수별 준수율 곡선
- `reports/figures/compliance_by_token_length.png` — 토큰 길이별 준수율
- `reports/figures/rule_turn_heatmap.png` — 규칙 수 × 턴 수 히트맵
- `reports/figures/compliance_by_target_rule.png` — 타겟 규칙별 준수율

## 핵심 결과

### 전체 준수율: 196/312 = 62.8%

### 턴 수 효과 (가설 지지)
| Turn | Compliance | 변화 |
|------|-----------|------|
| 0 | 70.8% | baseline |
| 2 | 68.1% | -2.7%p |
| 4 | 62.5% | -8.3%p |
| 6 | 61.1% | -9.7%p |
| 8 | 56.9% | -13.9%p |

→ 턴 수 증가에 따라 단조 감소. 70.8% → 56.9% (13.9%p 하락)

### 토큰 길이 효과 (가설 지지)
| Length | Compliance |
|--------|-----------|
| none (baseline) | 70.8% |
| short (~100tok) | 66.7% |
| medium (~300tok) | 65.6% |
| long (~500tok) | 54.2% |

→ 토큰 길이 증가에 따라 감소. 특히 long에서 급락 (-16.6%p vs baseline)

### 타겟 규칙별 준수율
| Target Rule | Compliance | n | 비고 |
|------------|-----------|---|------|
| Rule 1 ([TERMINAL_READY]) | 75.0% | 260 | 접두어 출력 — 비교적 쉬운 규칙 |
| Rule 3 (비밀번호 보호) | 1.9% | 52 | 비밀번호 거부하며 노출 패턴 |

⚠️ **현재 실험은 2개 타겟 규칙만 테스트** — probe_targets 설정에서 Rule 8/14/20 등 추가 규칙이 probes_per_condition=2 제한에 의해 선택되지 않음

### 규칙 수 × 턴 수 히트맵
```
         T 0   T 2   T 4   T 6   T 8
R  1:    25%    0%    0%    0%    0%   ← Rule 3만 테스트 (항상 실패)
R  3:   100%  100%   92%   83%   75%   ← Rule 1 위주, 턴 증가시 하락
R  5:    75%   75%   67%   67%   58%
R 10:    75%   83%   67%   67%   67%
R 15:    75%   75%   75%   75%   67%
R 20:    75%   75%   75%   75%   75%
```

### Baseline Hard Limit
- Turn 0 × Rule 20: 3/4 = **75%** (threshold ≥ 80%) → **경계 미달**
- 원인: 4건 중 1건이 Rule 3 (비밀번호) 타겟으로 실패
- Rule 1 타겟만 보면 3/3 = 100%

## 발견된 한계점

1. **타겟 규칙 다양성 부족**: 312건 중 260건이 Rule 1, 52건이 Rule 3만 테스트. Rule 8/14/20 등 미테스트
2. **Rule 3 Floor Effect**: 비밀번호 보호 규칙은 턴 수와 무관하게 ~2% compliance (구조적 실패)
3. **Rule 1 Ceiling Effect**: [TERMINAL_READY] 접두어는 비교적 쉬워 75% 유지

## 수정된 파일 목록
- `reports/evaluation_summary.json` (신규)
- `reports/scored_results.jsonl` (신규)
- `reports/figures/compliance_by_turn.png` (신규)
- `reports/figures/compliance_by_token_length.png` (신규)
- `reports/figures/rule_turn_heatmap.png` (신규)
- `reports/figures/compliance_by_target_rule.png` (신규)

## 다음 단계
- Phase 2: 압축 기법 적용 후 동일 312건 inference
- 또는: probe_targets 다양화 후 재실행 (Rule 8/14/20 테스트 추가)

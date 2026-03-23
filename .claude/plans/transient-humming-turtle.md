# Phase 2 Plan: Context Compression as System Prompt Defense

## Context
Phase 1에서 multi-turn 대화에서 system prompt compliance가 turn 수 증가에 따라 degradation되는 현상을 측정하는 파이프라인을 완성했다. Phase 2에서는 기존 context compression 기법을 적용하여 이 degradation을 방어할 수 있는지 실험한다.

**핵심 가설:** 중간 turn들을 압축하면 system prompt에 대한 attention이 유지되어 compliance degradation이 완화된다.

---

## 1. Compression Methods (4종)

| Method | 추가 API 비용 | 설명 |
|--------|-------------|------|
| **A. Sliding Window** | 없음 | 최근 N턴만 유지, system prompt 고정. 가장 단순한 baseline |
| **B. Selective Context** | 없음 | tiktoken 기반 token-level pruning. 정보량 낮은 토큰 제거 (Li et al., 2023) |
| **C. Turn Summarization** | 소량 | cheap 모델로 각 intermediate turn을 1문장 요약 |
| **D. System Prompt Reinforcement** | 없음 | 매 K턴마다 rule reminder 삽입 (압축이 아닌 방어 injection) |

**불변 원칙:** system_prompt와 probe_turn은 어떤 method도 수정하지 않는다.

---

## 2. New Files

```
src/compression/                    ← NEW module
├── __init__.py
├── CLAUDE.md
├── base.py                         # BaseCompressor ABC
├── sliding_window.py               # Method A
├── selective_context.py            # Method B
├── summarize_turns.py              # Method C (async, API call)
├── system_prompt_reinforce.py      # Method D
└── apply_compression.py            # Orchestrator: cases → compressed cases

configs/compression.yaml            ← NEW config
tests/test_compression.py           ← NEW tests
```

## 3. Modified Files

| File | 변경 내용 |
|------|----------|
| `src/models/open_router_request.py` | experiment case dict 입력 수용, hardcoded 경로 제거, checkpoint/resume |
| `src/evaluation/evaluation.py` | Phase 2 metrics 추가, hardcoded 경로 제거 |
| `src/utils/visualize.py` | compression method별 비교 그래프 |
| `CLAUDE.md` | file map, data flow 업데이트 |
| `requirements.txt` | 필요시 추가 의존성 |

---

## 4. Config Schema: `configs/compression.yaml`

```yaml
compression_methods:
  sliding_window:
    enabled: true
    window_sizes: [3, 5, 10]       # 최근 N턴 유지
  selective_context:
    enabled: true
    target_ratios: [0.5, 0.75]     # 원본 대비 보존 비율
  summarize_turns:
    enabled: true
    model: "google/gemini-2.0-flash-lite"
    max_summary_tokens: 50
  system_prompt_reinforce:
    enabled: true
    injection_intervals: [3, 5]    # 매 N턴마다 reminder

paths:
  input_cases: "data/processed/experiment_cases.jsonl"
  output_dir: "data/processed/compressed_cases/"

filter:
  min_turn_count: 5  # baseline(turn=0)은 compression 불필요
```

---

## 5. Extended Data Schema

기존 experiment case에 추가되는 필드:

```python
{
    # 기존 필드 모두 유지 + 아래 추가
    "original_case_id": str,        # Phase 1 원본 case_id 참조
    "condition": {
        ...existing...,
        "compression_method": str,   # "none"|"sliding_window"|"selective_context"|...
        "compression_params": dict,  # {"window_size": 5} 등
    },
    "compression_metadata": {
        "original_token_count": int,
        "compressed_token_count": int,
        "compression_ratio": float,  # compressed / original
    }
}
```

---

## 6. Data Flow (Phase 2)

```
Phase 1 output (기존):
  data/processed/experiment_cases.jsonl (104 cases, compression="none")
      ↓
apply_compression.py (compression.yaml 읽고 8개 variant 생성)
      ↓
  data/processed/compressed_cases/
  ├── sliding_window_3/experiment_cases.jsonl
  ├── sliding_window_5/...
  ├── sliding_window_10/...
  ├── selective_context_050/...
  ├── selective_context_075/...
  ├── summarize_turns/...
  ├── reinforce_3/...
  └── reinforce_5/...
      ↓
open_router_request.py (refactored)
      ↓
  data/outputs/{model}/{compression_method}/results.jsonl
      ↓
evaluation.py (refactored)
      ↓
  reports/figures/ (Phase 1 vs Phase 2 비교 그래프)
```

---

## 7. Experiment Scale

| Category | Cases |
|----------|-------|
| Phase 1 baseline (turn>0, compression=none) | ~100 |
| Sliding window (3 variants) | ~300 |
| Selective context (2 variants) | ~200 |
| Summarize turns (1 variant) | ~100 |
| System prompt reinforce (2 variants) | ~200 |
| **Total new inference calls** | **~800** |

Phase 1의 "none" 결과는 control로 재사용.

---

## 8. Phase 2 Metrics

| Metric | 수식 |
|--------|------|
| Compression ratio | compressed_tokens / original_tokens |
| Compliance preservation | compliance_compressed / compliance_none |
| Defense effectiveness | (compliance_compressed − compliance_none) / (1 − compliance_none) |
| Token cost savings | 1 − compression_ratio |

---

## 9. Implementation Order

### Sprint 1: Compression Foundation
1. `src/compression/base.py` — BaseCompressor ABC
2. `configs/compression.yaml`
3. `src/compression/sliding_window.py` — 가장 단순, 아키텍처 검증용
4. `src/compression/apply_compression.py` — orchestrator
5. `tests/test_compression.py` — sliding window 테스트
6. **검증:** sample 5 cases → compressed output 확인

### Sprint 2: Local Compression Methods
7. `src/compression/selective_context.py` — token_utils.py 재사용
8. `src/compression/system_prompt_reinforce.py`
9. 테스트 추가
10. **검증:** 전체 100 cases 처리, compression ratio 확인

### Sprint 3: LLM-Based Compression
11. `src/compression/summarize_turns.py` — async API call
12. mocked API 테스트
13. **검증:** 요약 품질 + 토큰 감소율 확인

### Sprint 4: Inference Pipeline Refactor
14. `src/models/open_router_request.py` 리팩터링
    - experiment case dict 직접 수용
    - hardcoded 경로 제거, logging 사용
    - checkpoint/resume 지원
15. 소규모 batch 테스트 (method당 5 cases)

### Sprint 5: Evaluation & Visualization
16. `src/evaluation/evaluation.py` 리팩터링
    - Phase 2 metrics 추가
    - hardcoded 경로/print 제거
17. `src/utils/visualize.py` 확장
    - compression method별 compliance curve
    - compression ratio vs compliance scatter
18. CLAUDE.md 업데이트

### Sprint 6: Full Experiment
19. 전체 ~800 cases inference 실행
20. evaluation + visualization 생성

---

## 10. Verification

- **Unit:** 각 compressor에서 system_prompt, probe_turn 불변 assert
- **Integration:** "none" compression으로 Phase 1 결과 재현 확인
- **Sanity:** selective_context ratio=0.5 → ~50% 토큰 감소 확인
- **E2E:** 5 cases × 4 methods → compress → infer → evaluate → 그래프 생성

---

## Critical File References

| Purpose | Path |
|---------|------|
| Experiment case schema + generation | `src/data_pipeline/generate_experiment_cases.py` |
| Token counting (재사용) | `src/data_pipeline/token_utils.py` |
| Current inference client | `src/models/open_router_request.py` |
| Current evaluation | `src/evaluation/evaluation.py` |
| Pipeline config (pattern 참조) | `configs/preprocess.yaml` |

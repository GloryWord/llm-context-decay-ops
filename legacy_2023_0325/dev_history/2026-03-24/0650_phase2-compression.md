# Phase 2: Context Compression as System Prompt Defense

**Date:** 2026-03-24
**Duration:** ~2 hours (including ~57min inference time)

## Summary
Implemented 4 context compression methods and ran full experiment (436 inference calls) to test whether compression mitigates system prompt compliance degradation in multi-turn conversations.

## What Was Built

### New Module: `src/compression/`
| File | Description |
|------|-------------|
| `base.py` | BaseCompressor ABC |
| `sliding_window.py` | Method A: Keep last N turns (window=3,5,10) |
| `selective_context.py` | Method B: Token-level pruning by info score (ratio=0.5,0.75) |
| `summarize_turns.py` | Method C: LLM-based turn summarization via OpenRouter |
| `system_prompt_reinforce.py` | Method D: Periodic rule reminder injection (interval=3,5) |
| `apply_compression.py` | Orchestrator — reads Phase 1 cases, outputs 8 compressed variants |

### New Config
- `configs/compression.yaml` — compression method parameters

### Refactored Files
- `src/models/open_router_request.py` — accepts experiment case dicts, checkpoint/resume, structured output
- `src/evaluation/evaluation.py` — rule-based scoring (IFEval constraints), Phase 2 metrics
- `src/utils/visualize.py` — compliance curves, compression vs compliance scatter, defense effectiveness bars
- `CLAUDE.md` — updated file map, data flow, phase status

### Tests
- `tests/test_compression.py` — 23 tests (7 sliding_window + 6 selective_context + 6 reinforce + 4 summarize_turns)

## Experiment Results

### Scale
- Baseline (no compression): 52 cases
- Compressed: 8 variants x 48 cases = 384 cases
- Total inference calls: 436

### Key Findings

| Method | Avg Compression Ratio | Avg Compliance Rate | Defense Effectiveness |
|--------|----------------------|--------------------|-----------------------|
| None (baseline) | 1.0 | 0.50 | — |
| Sliding Window | 0.71 | 0.53 | 0.07 (marginal) |
| Selective Context | 0.81 | 0.56 | 0.12 (slight) |
| **Turn Summarization** | **0.50** | **0.81** | **0.63 (strong)** |
| Prompt Reinforcement | 1.06 | 0.50 | 0.00 (no effect) |

**Turn Summarization was the most effective defense**, achieving ~81% compliance (vs 50% baseline) with 50% token reduction. Defense effectiveness of 0.63 means it recovered 63% of the gap between baseline and perfect compliance.

**Prompt Reinforcement showed zero effect** — injecting rule reminders did not improve compliance at all.

**Sliding Window and Selective Context showed marginal improvement** — simple context reduction helps slightly but is not sufficient alone.

### Interpretation
- Compliance degradation appears driven by contextual noise, not just context length
- Semantic compression (summarization) preserves key information while removing noise
- Naive truncation and token pruning are insufficient
- Active rule reinforcement is ineffective (model may learn to ignore repeated reminders)

## OpenRouter API Usage
| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Total usage ($) | 0.3373 | 3.9026 | **$3.5654** |
| Monthly usage ($) | 0.3005 | 3.8659 | $3.5654 |

### Cost Breakdown (estimated)
- Baseline inference (52 cases): ~$0.50
- Compression inference (384 cases): ~$2.90
- Turn summarization compression: ~$0.16
- Total: ~$3.57

## Output Files
- `data/processed/compressed_cases/{8 variants}/experiment_cases.jsonl`
- `data/outputs/google_gemini-3.1-flash-lite-preview/{9 dirs}/results.jsonl`
- `reports/evaluation_summary.json`
- `reports/scored_results.jsonl`
- `reports/figures/compliance_curves.png`
- `reports/figures/compression_vs_compliance.png`
- `reports/figures/defense_effectiveness.png`

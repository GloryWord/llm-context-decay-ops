# Phase 2-3 Research Plan

> Warning: Not auto-loaded.
> Usage: *"Read docs/phase2-research-plan.md and design Phase 2"*

---

## Phase 2: Evaluation Enhancement (Planned)

### Goal
Introduce LLM-as-Judge for qualitative assessment of open-ended responses.

### Tasks
1. **LLM Judge Prompt Design**
   - Define criteria: accuracy, logical consistency, completeness
   - Construct few-shot examples

2. **Judge Reliability Validation**
   - Measure Cohen's Kappa vs. human evaluators
   - Target: κ ≥ 0.7

3. **Metric Expansion**
   - Add BLEU, ROUGE
   - Per-category breakdown analysis

### File Structure Changes
```
src/evaluation/
├── evaluation.py         (existing)
├── metrics.py            (existing)
├── llm_judge.py          ← new
└── human_eval_compare.py ← new
```

---

## Phase 3: Multimodal Extension (Under Review)

### Goal
Expand evaluation scope to include image-text datasets.

### Prerequisites
- Phase 2 complete with validated judge reliability
- Confirm Vision model API support (OpenRouter)

### Tasks
1. Build image-text pair datasets
2. Add image processing logic to `data_pipeline/`
3. Research multimodal metric application strategies

---

## References
- [OpenRouter API Docs](https://openrouter.ai/docs)
- LLM-as-Judge: Zheng et al., 2023 "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"
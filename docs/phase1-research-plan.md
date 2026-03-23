# Research Project: Measuring System Prompt Compliance Degradation in Multi-Turn Conversations
# Phase 1 Plan

## Objective
Quantify when and under what conditions system prompt compliance degrades as turns accumulate in multi-turn conversations.

## Experiment Design

### Pipeline
```
System Prompt (rules + scoring fn from RuLES)
    ↓
N intermediate turns (varies by case)
    ↓
Probe turn (question designed to elicit rule violation)
    ↓
Auto-score (compliant=1 / violation=0)
    ↓
Output: compliance rate curve by turn count x condition
```

### Test Cases

| Case | Description | Intermediate Turns | Turn Counts |
|------|-------------|-------------------|-------------|
| 1 | Baseline | None (system prompt → probe directly) | 0 |
| 2 | Normal turn accumulation | ShareGPT user msgs + pre-generated model responses | 5, 10, 15, 20 |
| 3 | Hard turn accumulation | MultiChallenge conversations | 5, 10, 15, 20 |

### Independent Variables (5 total)

| Variable | Levels | Values |
|----------|--------|--------|
| Turn count | 5 | 0, 5, 10, 15, 20 |
| Conversation difficulty | 2 | normal (ShareGPT) / hard (MultiChallenge) |
| System prompt rule count | 2 | few (1) / many (3-5) |
| Probe intensity | 2 | basic / redteam |
| Tokens per turn | 2 | short (~100tok) / long (~500tok) |

### Total Experiments: ~104 (2 probes per condition)

- Baseline (turns=0): rule count 2 x probe intensity 2 = 4
- Normal turns: 4 x 2 x 2 x 2 = 32 (x 2 probes = 64)
- Hard turns: 4 x 2 x 2 = 16 (token length fixed; MultiChallenge content is fixed)

## Datasets

### Probe (system prompt compliance measurement)
- **Primary: RuLES** — built-in system prompt vs user conflict scenarios, 3 tiers (benign/basic/redteam), 1,695 test cases, programmatic auto-scoring
  - Paper: "Can LLMs Follow Simple Rules?" (arXiv:2311.04235)
  - Use: select 10-20 redteam cases
- **Secondary: IFEval** — format compliance (">=400 words", "output JSON", etc.), no LLM judge needed
  - Paper: "Instruction-Following Evaluation for Large Language Models" (arXiv:2311.07911)
  - HuggingFace: google/IFEval

### Intermediate Turns - Normal (Case 2)
- **ShareGPT** — ~90k real user-ChatGPT conversation logs
  - HuggingFace: anon8231489123/ShareGPT_Vicuna_unfiltered
  - Usage: extract user messages → pre-generate assistant responses using the target model → use fixed (user, assistant) pairs as intermediate turns
  - Note: do not use original GPT responses; pre-generate with target model to avoid confounding

### Intermediate Turns - Hard (Case 3)
- **MultiChallenge** — by Scale AI, up to 10 turns, 4 challenge categories
  - Paper: arXiv:2501.17399
  - GitHub: ekwinox117/multi-challenge
  - Categories: Instruction Retention, Inference Memory, Reliable Versioned Editing, Self-Coherence
  - Frontier models score <50% (unsaturated)

### Excluded Datasets

| Dataset | Reason |
|---------|--------|
| MT-Eval | Saturated at frontier model level; MultiChallenge supersedes it |
| StructFlowBench | Measures inter-turn structural flow; requires content modification; low ROI |
| LIFBench | Single-turn long-context; usable as probe but scoring is complex and token-heavy; RuLES is more efficient |

## Scoring

| Rule Type | Probe Dataset | Scoring Method |
|-----------|---------------|----------------|
| Security/safety (secret key protection, PII refusal, etc.) | RuLES | Programmatic (string matching) |
| Format (word count, JSON, keyword inclusion, etc.) | IFEval | Rule-based validation (automated code) |

## Expected Output
Compliance rate curves (X: turn count, Y: compliance rate) per case, isolating:
1. Pure turn accumulation forgetting effect (Case 2 vs Case 1)
2. Hard conversation degradation effect (Case 3 vs Case 2)
3. Effects of rule count, probe intensity, and tokens-per-turn

## Future Work (Phase 2-3)
- Details: docs/phase2-research-plan.md (do not load by default)
- Phase 2: Apply existing context compression methods as system prompt defense; measure effectiveness
- Phase 3: Propose hybrid compression strategy dedicated to system prompt preservation

## Technical Setup
- Language: Python
- Target model: `google/gemini-3.1-flash-lite-preview` family (extensible)
- Minimize API cost: target ~100 high-quality test cases
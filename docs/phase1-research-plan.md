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
| 2 | Normal turn accumulation | ShareGPT user msgs + pre-generated model responses | 2, 4, 6 |
| 3 | Hard turn accumulation | MultiChallenge conversations | 2, 4, 6 |

### Independent Variables (5 total)

| Variable | Levels | Values | Rationale |
|----------|--------|--------|-----------|
| Turn count | 4 | 0, 2, 4, 6 | Max 6: turn 6 × long(500tok) ≈ 3,000tok (collapse threshold) |
| Conversation difficulty | 2 | normal (ShareGPT) / hard (MultiChallenge) | |
| System prompt rule count | 5 | 1, 3, 5, 10, 20 | Scaling curve: verify compliance → 0 as rules → 20 |
| Probe intensity | 2 | basic / redteam | |
| Tokens per turn | 3 | short (~100tok) / medium (~300tok) / long (~500tok) | 3 levels to capture ~3,000tok threshold precisely |

#### Design Rationale

**Turn count (max 6):**
- Prior research shows compliance collapse begins around ~3,000 cumulative context tokens
- Turn 6 × long(500tok) = ~3,000tok aligns with this threshold
- Turn 20 × long(500tok) = ~10,000tok is already deep in contamination zone — no additional information
- Finer intervals (0, 2, 4, 6) reveal early degradation patterns

**Rule count (1 → 20):**
- Prior experiments observed compliance approaching 0 with ~20 guardrail rules
- System prompt should occupy ≤5–10% of total context; beyond this, attention dilutes across irrelevant rules
- Levels 1, 3, 5 overlap with prior Phase 1 for continuity; 10 and 20 are new extreme conditions
- Rule count 1–5: sourced from RuLES scenarios; 10, 20: hybrid IFEval + RuLES composite

**Token length per turn (3 levels):**
- Turn 6 × short(100) = 600tok — well below threshold
- Turn 6 × medium(300) = 1,800tok — approaching threshold
- Turn 6 × long(500) = 3,000tok — at threshold

### Total Experiments: ~260 (2 probes per condition)

- Baseline (turns=0): rule_count(5) × probe_intensity(2) × probe_set(2) = 20
- Normal turns: turn_count(3) × rule_count(5) × probe_intensity(2) × token_length(3) × probe_set(2) = 180
- Hard turns: turn_count(3) × rule_count(5) × probe_intensity(2) × probe_set(2) = 60
  (token_length fixed for MultiChallenge)

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
Compliance rate curves per case, isolating:
1. Pure turn accumulation forgetting effect (Case 2 vs Case 1)
2. Hard conversation degradation effect (Case 3 vs Case 2)
3. Rule count scaling curve (X: rule count 1→20, Y: compliance rate) — expect sigmoid-like decay
4. Token threshold analysis (cumulative tokens vs compliance)
5. Interaction effects: rule_count × turn_count, token_length × turn_count

## Future Work (Phase 2-3)
- Details: docs/phase2-research-plan.md (do not load by default)
- Phase 2: Apply existing context compression methods as system prompt defense; measure effectiveness
- Phase 3: Propose hybrid compression strategy dedicated to system prompt preservation

## Technical Setup
- Language: Python
- Target model: `google/gemini-3.1-flash-lite-preview` family (extensible)
- Minimize API cost: target ~260 high-quality test cases
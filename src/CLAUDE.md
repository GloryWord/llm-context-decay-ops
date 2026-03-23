# src/ Source Overview

## Module Structure
```
src/
├── data_pipeline/   ← data loading, preprocessing, experiment case generation
├── evaluation/      ← metric calculation
├── models/          ← API calls & prompts
└── utils/           ← shared utilities
```

Each subdirectory has its own CLAUDE.md (loaded on directory access).

## Dependencies
```
data_pipeline ──→ models ──→ evaluation
     ↓                           ↓
   utils  ←──────────────────── utils
```

## Common Data Schema

### Experiment Case (processed — `data/processed/experiment_cases.jsonl`)
```python
{
    "case_id": str,              # "exp_001"
    "condition": {
        "turn_count": int,       # 0, 5, 10, 15, 20
        "difficulty": str,       # "baseline" | "normal" | "hard"
        "rule_count_level": str, # "few" | "many"
        "probe_intensity": str,  # "basic" | "redteam"
        "token_length": str      # "short" | "long" | "fixed" | "none"
    },
    "system_prompt": str,        # rendered system prompt with rules
    "intermediate_turns": list,  # [{role, content}, ...]
    "intermediate_turns_type": str,  # "none" | "user_only" | "full"
    "probe_turn": dict,          # {role: "user", content: "..."}
    "scoring": {
        "type": str,             # "programmatic" | "rule_based"
        "dataset": str,          # "rules" | "ifeval"
        "check_description": str,
        "params": dict           # optional scoring params
    }
}
```

### Output Record (outputs — `data/outputs/`)
```python
{
    "case_id": str,
    "model": str,        # model identifier
    "response": str,     # model response to probe
    "compliant": int,    # 1 (compliant) or 0 (violation)
    "latency_ms": float,
    "tokens_used": int,
    "timestamp": str     # ISO 8601
}
```

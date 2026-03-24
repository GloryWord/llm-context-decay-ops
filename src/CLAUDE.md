# src/ Source Overview

## Module Structure
```
src/
├── data_pipeline/   ← data loading, preprocessing, experiment case generation
├── compression/     ← context compression methods (Phase 2)
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

## Common Data Schema (v2)

### Experiment Case — Case 2 (processed — `data/processed/experiment_cases.jsonl`)
```python
{
    "case_id": str,              # "exp_0001"
    "condition": {
        "turn_count": int,       # 0, 2, 4, 6, 8
        "difficulty": str,       # "baseline" | "normal" | "alignment_tax"
        "rule_count_level": int, # 1, 3, 5, 10, 15, 20
        "probe_intensity": str,  # "basic" | "redteam" | "task"
        "token_length": str      # "short" | "medium" | "long" | "none" | "fixed"
    },
    "system_prompt": str,        # Project Aegis rendered rules
    "rendered_user_message": str, # single user message (history embedded + probe)
    "intermediate_turns_type": str,  # "none" | "user_only_embedded" | "full"
    "probe_id": str,             # "aegis_L5_R3_basic_P0"
    "target_rule": int,          # rule being tested
    "scoring": {
        "type": str,             # "programmatic" | "task_accuracy"
        "dataset": str,          # "project_aegis" | "multichallenge"
        "check_description": str,
        "target_rule": int,
        "rule_ids": list[int]    # all rules in system prompt
    },
    "token_counts": {
        "system_prompt_tokens": int,
        "user_message_tokens": int,
        "total_context_tokens": int   # final rendered string tokenized
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

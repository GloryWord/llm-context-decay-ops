# src/ Source Overview

## Module Structure
```
src/
├── data_pipeline/   ← data loading & preprocessing
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

### Input Record (processed)
```python
{
    "id": str,           # unique identifier
    "question": str,     # question text
    "answer": str,       # ground truth
    "category": str,     # question type
    "difficulty": int    # 1-5
}
```

### Output Record (outputs)
```python
{
    "id": str,
    "model": str,        # model identifier
    "prompt": str,       # actual input prompt
    "response": str,     # model response
    "latency_ms": float,
    "tokens_used": int,
    "timestamp": str     # ISO 8601
}
```
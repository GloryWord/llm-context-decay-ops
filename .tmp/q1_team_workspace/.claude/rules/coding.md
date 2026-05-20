# Coding Rules

## Python Style
- Python 3.10+ syntax
- Type hints required: `def func(x: int) -> str:`
- Docstrings: Google style
- Line length: 100 chars max
- Formatter: `black`, Linter: `ruff`

## Import Order (isort)
```python
# 1. stdlib
import os
import json

# 2. third-party
import pandas as pd
import numpy as np

# 3. local
from src.utils.json_prettier import load_json
```

## Naming
| Target | Convention | Example |
|--------|------------|---------|
| var/func | `snake_case` | `load_dataset` |
| class | `PascalCase` | `EvaluationResult` |
| constant | `UPPER_SNAKE` | `MAX_TOKENS` |
| file | `snake_case.py` | `open_router_request.py` |

## Error Handling
```python
# API calls: always include retry logic
# File I/O: explicit exception handling
try:
    result = call_api(prompt)
except APIError as e:
    logger.error(f"API call failed: {e}")
    raise
```

## Logging
- Use `logging` module (no `print`)
- Levels: DEBUG (dev) / INFO (pipeline) / ERROR (exceptions)

## Data Storage
| Type | Path | Format |
|------|------|--------|
| Intermediate | `data/processed/` | JSON Lines (`.jsonl`) |
| Final output | `data/outputs/` | JSON |
| Config | `configs/` | YAML |

## Testing
- Unit tests for all public functions
- File: `tests/test_<module>.py`
- Mock all API calls

## Prohibited
- No hardcoded paths to files in `data/` in source code
- No API keys in code (use `.env` or env vars)
- No `print()` debugging (use logger)
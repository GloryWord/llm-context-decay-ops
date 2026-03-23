# utils module

## Purpose
Shared file I/O, logging, and visualization utilities used across the project.

## Files
| File | Role |
|------|------|
| `json_prettier.py` | JSON/JSONL read/write and formatting |
| `visualize.py` | Evaluation result visualization (matplotlib/seaborn) |
| `logger.py` | Project-wide logger config |

## Common Usage
```python
from src.utils.json_prettier import load_jsonl, save_jsonl
from src.utils.logger import get_logger
from src.utils.visualize import plot_evaluation

logger = get_logger(__name__)
records = load_jsonl("data/processed/dataset.jsonl")
save_jsonl(results, "data/outputs/results.jsonl")
plot_evaluation(eval_result, save_path="reports/figures/eval.png")
```

## Logger Config
```python
# Log levels
DEBUG   → detailed info during development
INFO    → pipeline progress
WARNING → unexpected situations (missing data, etc.)
ERROR   → exceptions and failures

# Output: console + data/outputs/logs/<date>.log
```
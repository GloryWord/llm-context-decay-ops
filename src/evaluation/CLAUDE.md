# evaluation module

## Role
Compare model outputs (`data/outputs/`) against ground truth (`data/raw/`), compute metrics, save to `reports/`.

## Files
| File | Role |
|------|------|
| `evaluation.py` | Main evaluation logic |
| `metrics.py` | Individual metric functions (accuracy, F1, etc.) |

## Supported Metrics (Phase 1)
- **Exact Match (EM)**: Full string match against ground truth
- **Token-level F1**: F1 score based on token overlap
- **Accuracy by Category**: Per-category accuracy

## Interface
```python
# evaluation.py
def evaluate(outputs_path: str, raw_path: str) -> EvaluationResult: ...
def save_report(result: EvaluationResult, output_dir: str) -> None: ...
```

## Output Schema
```python
# EvaluationResult
{
    "model": str,
    "total": int,
    "exact_match": float,      # 0.0 ~ 1.0
    "token_f1": float,
    "by_category": dict[str, float],
    "evaluated_at": str
}
```

## Report Paths
| Format | Path |
|--------|------|
| JSON | `reports/<model_id>_eval.json` |
| Plot | `reports/figures/<model_id>_eval.png` |
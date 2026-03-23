# data_pipeline

## Role
Load raw data (`data/raw/`), preprocess into model input format, save to `data/processed/`.

## Files
| File | Role |
|------|------|
| `load_datasets.py` | Raw data loading, schema validation |
| `preprocess.py` | Text normalization, tokenization |
| `augment.py` | Data augmentation (optional) |

## Interface
```python
# load_datasets.py
def load_raw(path: str) -> list[dict]: ...
def validate_schema(records: list[dict]) -> bool: ...
def save_processed(records: list[dict], output_path: str) -> None: ...
```

## I/O
- Input: `data/raw/*.json` or `data/raw/*.jsonl`
- Output: `data/processed/<dataset_name>.jsonl`

## Constraints
- Never modify `data/raw/`
- Load preprocessing params from `configs/preprocess.yaml`
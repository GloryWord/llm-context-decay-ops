# System Architecture

> Not auto-loaded. Reference explicitly when needed.

## Pipeline

```
[data/raw/]
    │
    ▼
[src/data_pipeline/load_datasets.py]
    │  schema validation, normalization, tokenization
    ▼
[data/processed/*.jsonl]
    │
    ▼
[src/models/open_router_request.py]
    │  OpenRouter API call (batch)
    ▼
[data/outputs/<model>/<timestamp>.jsonl]
    │
    ▼
[src/evaluation/evaluation.py]
    │  EM, Token F1, Category Accuracy
    ▼
[reports/<model>_eval.json]
    │
    ▼
[src/utils/visualize.py]
    │
    ▼
[reports/figures/<model>_eval.png]
```

## Config Structure

```
configs/
├── preprocess.yaml   ← preprocessing params
├── models.yaml       ← API settings, model list
└── evaluation.yaml   ← metric selection
```

## Environment Variables

```bash
OPENROUTER_API_KEY=<your_key>
LOG_LEVEL=INFO          # DEBUG | INFO | WARNING | ERROR
DATA_DIR=data/          # data root path (default)
```
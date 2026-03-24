# data_pipeline

## Role
Download raw datasets, preprocess into experiment-ready format, generate ~260 experiment cases for Phase 1 v2.

## Files
| File | Role |
|------|------|
| `load_datasets.py` | Pipeline entry point — orchestrates download → preprocess → case generation |
| `download_datasets.py` | Downloads RuLES, IFEval, ShareGPT, MultiChallenge to `data/raw/` |
| `token_utils.py` | Shared token counting utilities (tiktoken cl100k_base) |
| `preprocess_rules.py` | RuLES probe extraction with rule_count classification |
| `preprocess_ifeval.py` | IFEval format constraint separation + auto-scorable filtering |
| `preprocess_sharegpt.py` | ShareGPT user turn extraction with quality/token-length filtering |
| `preprocess_multichallenge.py` | MultiChallenge conversation turn extraction (excludes TARGET_QUESTION) |
| `generate_experiment_cases.py` | Combines probes + intermediate turns into experiment cases |

## Interface
```python
# load_datasets.py — full pipeline
def run_pipeline(config_path: str, skip_download: bool = False) -> None: ...

# Individual modules — each returns processed records
def preprocess_rules(config_path: str) -> list[dict]: ...
def preprocess_ifeval(config_path: str) -> list[dict]: ...
def preprocess_sharegpt(config_path: str) -> dict[str, list[dict]]: ...
def preprocess_multichallenge(config_path: str) -> list[dict]: ...
def generate_cases(config_path: str) -> list[dict]: ...
```

## I/O
- Config: `configs/preprocess.yaml`
- Input: `data/raw/{rules/, ifeval/, sharegpt/, multichallenge/}`
- Output:
  - `data/processed/rules_probes.jsonl`
  - `data/processed/ifeval_probes.jsonl`
  - `data/processed/sharegpt_turns_short.jsonl`
  - `data/processed/sharegpt_turns_medium.jsonl`
  - `data/processed/sharegpt_turns_long.jsonl`
  - `data/processed/multichallenge_conversations.jsonl`
  - `data/processed/experiment_cases.jsonl`

## CLI
```bash
# Full pipeline
python -m src.data_pipeline.load_datasets --config configs/preprocess.yaml

# Skip download (raw data already exists)
python -m src.data_pipeline.load_datasets --config configs/preprocess.yaml --skip-download

# Individual modules
python -m src.data_pipeline.download_datasets --config configs/preprocess.yaml
python -m src.data_pipeline.preprocess_rules --config configs/preprocess.yaml
python -m src.data_pipeline.preprocess_ifeval --config configs/preprocess.yaml
python -m src.data_pipeline.preprocess_sharegpt --config configs/preprocess.yaml
python -m src.data_pipeline.preprocess_multichallenge --config configs/preprocess.yaml
python -m src.data_pipeline.generate_experiment_cases --config configs/preprocess.yaml
```

## Constraints
- Never modify `data/raw/`
- All preprocessing params from `configs/preprocess.yaml`
- No hardcoded file paths in source

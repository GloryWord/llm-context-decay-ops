# data_pipeline

## Role
Download raw datasets, preprocess into experiment-ready format, generate ~408 experiment cases for Phase 1 v2.

## Files
| File | Role |
|------|------|
| `load_datasets.py` | Pipeline entry point — orchestrates download → preprocess → case generation |
| `download_datasets.py` | Downloads RuLES, IFEval, ShareGPT, MultiChallenge to `data/raw/` |
| `token_utils.py` | Shared token counting (Qwen/Qwen3.5-9B AutoTokenizer) |
| `preprocess_rules.py` | RuLES probe extraction (legacy, retained for compatibility) |
| `preprocess_ifeval.py` | IFEval format constraint separation (legacy) |
| `preprocess_sharegpt.py` | ShareGPT user turn extraction with quality/token-length filtering |
| `preprocess_multichallenge.py` | MultiChallenge conversation turn extraction |
| `generate_multi_rule_probes.py` | **v2: Project Aegis 20-rule persona, probe generation, auto-scoring** |
| `generate_experiment_cases.py` | **v2: single-message embedding, total_context_tokens, Alignment Tax** |

## Interface
```python
# load_datasets.py — full pipeline
def run_pipeline(config_path: str, skip_download: bool = False) -> None: ...

# v2 modules
def generate_probes(config_path: str) -> list[dict]: ...      # generate_multi_rule_probes.py
def generate_cases(config_path: str) -> list[dict]: ...        # generate_experiment_cases.py
def score_rule(rule_id: int, response: str) -> bool: ...       # generate_multi_rule_probes.py

# Legacy modules
def preprocess_rules(config_path: str) -> list[dict]: ...
def preprocess_ifeval(config_path: str) -> list[dict]: ...
def preprocess_sharegpt(config_path: str) -> dict[str, list[dict]]: ...
def preprocess_multichallenge(config_path: str) -> list[dict]: ...
```

## I/O
- Config: `configs/preprocess.yaml`
- Input: `data/raw/{rules/, ifeval/, sharegpt/, multichallenge/}`
- Output:
  - `data/processed/aegis_probes.jsonl` (v2: Project Aegis probes)
  - `data/processed/sharegpt_turns_{short,medium,long}.jsonl`
  - `data/processed/multichallenge_conversations.jsonl`
  - `data/processed/experiment_cases.jsonl` (v2: single-message embedded)

## CLI
```bash
# Full pipeline
python -m src.data_pipeline.load_datasets --config configs/preprocess.yaml

# v2 modules
python -m src.data_pipeline.generate_multi_rule_probes --config configs/preprocess.yaml
python -m src.data_pipeline.generate_experiment_cases --config configs/preprocess.yaml

# Individual preprocessing
python -m src.data_pipeline.preprocess_sharegpt --config configs/preprocess.yaml
python -m src.data_pipeline.preprocess_multichallenge --config configs/preprocess.yaml
```

## Constraints
- Never modify `data/raw/`
- All preprocessing params from `configs/preprocess.yaml`
- No hardcoded file paths in source
- Token counting: always tokenize final rendered string, never arithmetic sum

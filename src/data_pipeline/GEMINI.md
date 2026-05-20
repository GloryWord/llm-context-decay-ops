# data_pipeline

## Status
- This folder mixes **legacy preprocessing routes** and **current case-generation helpers**.
- Canonical workflow/orchestration lives in `../../CODEX.md`.
- Before editing, verify whether the caller expects `experiment_cases_full.jsonl`, `experiment_cases.jsonl`, or another intermediate artifact.

## Key files
| File | Role |
|------|------|
| `download_datasets.py` | raw dataset acquisition helpers |
| `load_datasets.py` | config-driven orchestration for download/preprocess/generation |
| `token_utils.py` | tokenizer + token counting helpers |
| `preprocess_rules.py` | RuLES preprocessing (legacy/compatibility lane) |
| `preprocess_ifeval.py` | IFEval preprocessing |
| `preprocess_sharegpt.py` | ShareGPT turn extraction/filtering |
| `preprocess_multichallenge.py` | MultiChallenge turn extraction |
| `generate_multi_rule_probes.py` | rule prompt/probe generation + scoring helpers |
| `generate_experiment_cases.py` | embedded-message style case generation |

## Important neighboring entrypoints
- `scripts/generate_full_cases.py` currently matters for the main capstone full-factorial case set.
- This means not every production case artifact is born directly from this folder alone.

## Typical artifacts
- Raw inputs: `data/raw/*`
- Intermediate processed outputs: `data/processed/aegis_probes.jsonl`, `data/processed/sharegpt_turns_*.jsonl`, `data/processed/multichallenge_conversations.jsonl`
- Final case artifacts vary by route; verify the active script before changing schema or names.

## Local rules
- Never mutate `data/raw/` in-place.
- Token counts must be based on the final rendered content, not rough arithmetic sums.
- Keep dataset download/preprocess concerns separate from experiment-runner concerns.
- If you change a case schema, sync downstream evaluation/report/tests in the same task.

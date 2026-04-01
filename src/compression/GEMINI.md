# compression

## Role
Apply context compression methods to Phase 1 experiment cases as system prompt defense mechanisms. Each method transforms intermediate_turns while preserving system_prompt and probe_turn.

## Files
| File | Role |
|------|------|
| `base.py` | BaseCompressor ABC — all compressors inherit from this |
| `sliding_window.py` | Method A: keep last N turns |
| `selective_context.py` | Method B: token-level pruning by self-information |
| `summarize_turns.py` | Method C: LLM-based turn summarization |
| `system_prompt_reinforce.py` | Method D: periodic rule reminder injection |
| `apply_compression.py` | Orchestrator: reads cases, applies all methods, writes output |

## Interface
```python
# All compressors implement:
class BaseCompressor(ABC):
    def compress(
        self,
        system_prompt: str,
        intermediate_turns: list[dict],
        params: dict,
    ) -> tuple[list[dict], dict]: ...

    @property
    def method_name(self) -> str: ...

# Orchestrator:
def run_compression(config_path: str) -> dict[str, list[dict]]: ...
```

## I/O
- Config: `configs/compression.yaml`
- Input: `data/processed/experiment_cases.jsonl`
- Output: `data/processed/compressed_cases/{variant_name}/experiment_cases.jsonl`

## CLI
```bash
python -m src.compression.apply_compression --config configs/compression.yaml
```

## Invariants
- system_prompt is NEVER modified
- probe_turn is NEVER modified
- Each compressed case links back via `original_case_id`

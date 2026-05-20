# compression

## Status
- This folder is **Phase 2 / experimental defense-method work**, not the default capstone execution path.
- Only touch it when the task explicitly scopes compression, defense variants, or Phase 2 analysis.
- Canonical orchestration still lives in `../../CODEX.md`.

## Key files
| File | Role |
|------|------|
| `base.py` | `BaseCompressor` contract |
| `sliding_window.py` | recent-turn retention compressor |
| `selective_context.py` | selective pruning compressor |
| `summarize_turns.py` | summarization-based compressor |
| `system_prompt_reinforce.py` | reminder/reinforcement compressor |
| `apply_compression.py` | registration + batch application entrypoint |

## Working model
- Input cases are loaded from caller-chosen processed artifacts.
- Compression should preserve experiment traceability back to the original case.
- Output paths/configs are caller-driven; verify local config/artifact paths before running.

## Local rules
- Never silently change the meaning of `system_prompt` or the probe turn.
- Preserve enough metadata to map compressed cases back to originals.
- If compressor behavior changes, update `tests/test_compression.py` in the same task.
- Mark outputs `UNVERIFIED` when the referenced config/input artifact is missing.

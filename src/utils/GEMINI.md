# utils

## Status
- This folder contains small shared helpers used across scripts/modules.
- Canonical workflow/orchestration lives in `../../CODEX.md`.
- Keep these docs factual: they should describe what exists now, not planned helpers.

## Key files
| File | Role |
|------|------|
| `http_headers.py` | API-header construction with OpenRouter/vLLM distinctions |
| `json_pretter.py` | JSON formatting helper |
| `visualize.py` | plot generation helpers |

## Local rules
- Keep utilities small and reusable.
- Prefer pure helpers over hidden side effects.
- Visualization output paths are caller-driven; verify the active report/output directory before editing plot code.
- If a helper becomes a cross-module dependency, add/update tests where practical.

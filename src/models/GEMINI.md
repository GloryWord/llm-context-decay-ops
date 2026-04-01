# models

## Purpose
Request LLM inference via OpenRouter API; save responses to `data/outputs/`.

## Files
| File | Role |
|------|------|
| `open_router_request.py` | OpenRouter API client — async inference with retry/backoff |

## API Config
```python
# Required env var
OPENROUTER_API_KEY=...

# Defaults in open_router_request.py
DEFAULT_MODEL = "qwen/qwen3.5-9b"
MAX_RETRIES = 3
BACKOFF_BASE = 2
```

## Message Building (v2)
- `user_only_embedded` cases: system_prompt + single rendered_user_message
- `full` (Alignment Tax) cases: system_prompt + multi-turn intermediate_turns + probe
- `none` (baseline) cases: system_prompt + probe only

## Retry Policy
- Max 3 retries
- Exponential backoff: 2s -> 4s -> 8s
- On 429 (rate limit): wait before retry

## Output Path
- `data/outputs/<model_slug>/<variant>/results.jsonl`

## Constraints
- Never hardcode API keys
- Log all requests/responses (for debugging)

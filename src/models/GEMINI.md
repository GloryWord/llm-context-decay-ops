# models

## Status
- This folder is the **model request boundary**.
- Canonical workflow/orchestration lives in `../../CODEX.md`.
- Top-level experiment scripts may also call model endpoints directly, so keep request/header assumptions aligned across the repo.

## Key files
| File | Role |
|------|------|
| `open_router_request.py` | request helper for model inference |

## Environment expectations
Common repo-level environment variables include:
- `VLLM_API_URL`
- `VLLM_API_KEY`
- `EVAL_MODEL_NAME`
- `OPENROUTER_API_KEY`
- `JUDGE_MODEL_NAME`

## Local rules
- Never hardcode secrets.
- Keep OpenRouter vs local-vLLM header behavior aligned with `src/utils/http_headers.py`.
- When debugging request issues, log the chosen endpoint/model path clearly but avoid leaking credentials.
- If request/response schema changes, sync calling scripts and tests in the same task.

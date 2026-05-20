# tests/

## Status
- Tests are the **verification lane** for this repo.
- Canonical workflow/orchestration lives in `../CODEX.md`.
- If behavior changes, update/add tests before claiming completion whenever practical.

## Current test files
| File | Focus |
|------|------|
| `test_compliance_scorer.py` | rule scoring + compliance rate behavior |
| `test_compression.py` | compression method invariants |
| `test_http_headers.py` | header-building and vLLM/OpenRouter distinctions |

## Local rules
- Prefer targeted tests for the module you touched.
- Keep tests deterministic and offline; do not require live model/network calls.
- Use the smallest representative fixtures possible.
- If a dependency for verification is missing, report `UNVERIFIED` explicitly rather than pretending the test passed.

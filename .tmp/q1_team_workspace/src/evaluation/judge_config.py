"""Configuration helpers for OpenAI-compatible LLM judge endpoints.

The experiment can judge responses through either OpenRouter or a local
OpenAI-compatible server such as vLLM/llama.cpp.  This module centralizes the
environment-variable contract so runners and scorers do not hard-code one
provider.
"""

from __future__ import annotations

import json
import os
from typing import Any

from src.utils.http_headers import build_json_headers, is_openrouter_url


OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
LOCAL_JUDGE_CHAT_COMPLETIONS_URL = "http://210.179.28.26:18001/v1/chat/completions"

LOCAL_PROVIDER_ALIASES = {"vllm", "local", "local-vllm", "llama_cpp", "llamacpp", "gemma"}
OPENROUTER_PROVIDER_ALIASES = {"openrouter", "or"}


def normalize_judge_provider(provider: str | None) -> str:
    """Normalize judge provider aliases to ``openrouter`` or ``vllm``."""
    value = (provider or "").strip().lower()
    if value in LOCAL_PROVIDER_ALIASES:
        return "vllm"
    if value in OPENROUTER_PROVIDER_ALIASES:
        return "openrouter"
    return value or "openrouter"


def _env_first(env: dict[str, str], names: tuple[str, ...], default: str = "") -> str:
    """Return the first non-empty env value among ``names``."""
    for name in names:
        value = env.get(name)
        if value:
            return value
    return default


def _int_env(env: dict[str, str], name: str, default: int) -> int:
    """Parse a positive integer environment variable."""
    raw = env.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _default_extra_params(provider: str, model_name: str) -> dict[str, Any]:
    """Return provider/model-specific judge payload extras."""
    if provider == "openrouter" and "deepseek" in model_name.lower():
        # DeepSeek reasoning models on OpenRouter can return reasoning-only
        # content unless reasoning effort is disabled.
        return {"reasoning": {"effort": "none"}}
    return {}


def _extra_params_from_env(
    env: dict[str, str],
    provider: str,
    model_name: str,
) -> dict[str, Any]:
    """Parse optional JSON extras, falling back to safe provider defaults."""
    raw = env.get("JUDGE_EXTRA_PARAMS_JSON")
    if not raw:
        return _default_extra_params(provider, model_name)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("JUDGE_EXTRA_PARAMS_JSON must be valid JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError("JUDGE_EXTRA_PARAMS_JSON must decode to a JSON object")
    return parsed


def resolve_judge_config(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Resolve judge configuration from environment variables.

    Environment contract:
    - ``JUDGE_PROVIDER`` or ``JUDGE_BACKEND``: ``openrouter`` or ``vllm``.
    - ``JUDGE_API_URL``: direct override for chat-completions endpoint.
    - ``JUDGE_MODEL_NAME``: direct override for judge model name.
    - ``JUDGE_API_KEY``: direct override for bearer token.
    - OpenRouter defaults: ``JUDGE_OPENROUTER_*`` then ``OPENROUTER_API_KEY``.
    - Local defaults: ``JUDGE_VLLM_*`` then ``VLLM_JUDGE_*``.

    Judge temperature is intentionally fixed at 0.0; target-model temperature is
    configured separately by experiment runners.
    """
    env = env or os.environ

    explicit_url = env.get("JUDGE_API_URL", "")
    provider = normalize_judge_provider(
        env.get("JUDGE_PROVIDER") or env.get("JUDGE_BACKEND")
    )
    if not (env.get("JUDGE_PROVIDER") or env.get("JUDGE_BACKEND")) and explicit_url:
        provider = "openrouter" if is_openrouter_url(explicit_url) else "vllm"

    if provider == "vllm":
        api_url = explicit_url or _env_first(
            env,
            ("JUDGE_VLLM_API_URL", "VLLM_JUDGE_API_URL"),
            LOCAL_JUDGE_CHAT_COMPLETIONS_URL,
        )
        model_name = _env_first(
            env,
            ("JUDGE_MODEL_NAME", "JUDGE_VLLM_MODEL_NAME", "VLLM_JUDGE_MODEL_NAME"),
            "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit",
        )
        api_key = _env_first(
            env,
            ("JUDGE_API_KEY", "JUDGE_VLLM_API_KEY", "VLLM_JUDGE_API_KEY"),
            "",
        )
    else:
        provider = "openrouter"
        api_url = explicit_url or _env_first(
            env,
            ("JUDGE_OPENROUTER_API_URL",),
            OPENROUTER_CHAT_COMPLETIONS_URL,
        )
        model_name = _env_first(
            env,
            ("JUDGE_MODEL_NAME", "JUDGE_OPENROUTER_MODEL_NAME"),
            "deepseek/deepseek-r1",
        )
        api_key = _env_first(
            env,
            ("JUDGE_API_KEY", "JUDGE_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"),
            "",
        )

    extra_params = _extra_params_from_env(env, provider, model_name)

    return {
        "provider": provider,
        "api_url": api_url,
        "model_name": model_name,
        "api_key": api_key,
        "temperature": 0.0,
        "max_tokens": _int_env(env, "JUDGE_MAX_TOKENS", 256),
        "extra_params": extra_params,
    }


def build_judge_headers(config: dict[str, Any]) -> dict[str, str]:
    """Build request headers for a resolved judge config."""
    return build_json_headers(str(config["api_url"]), str(config.get("api_key", "")))


def build_judge_payload(
    messages: list[dict[str, str]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an OpenAI-compatible judge payload with temperature fixed at 0.0."""
    resolved = config or resolve_judge_config()
    payload: dict[str, Any] = {
        "model": resolved["model_name"],
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": resolved["max_tokens"],
    }
    payload.update(resolved.get("extra_params", {}))
    return payload


def judge_metadata(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return non-secret judge metadata suitable for result artifacts."""
    resolved = config or resolve_judge_config()
    return {
        "judge_provider": resolved["provider"],
        "judge_api_url": resolved["api_url"],
        "judge_model": resolved["model_name"],
        "judge_temperature": 0.0,
        "judge_max_tokens": resolved["max_tokens"],
        "judge_extra_params": resolved.get("extra_params", {}),
    }

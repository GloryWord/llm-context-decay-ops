"""Tests for configurable LLM-judge endpoint resolution."""

from __future__ import annotations

from src.evaluation.judge_config import (
    build_judge_headers,
    build_judge_payload,
    judge_metadata,
    resolve_judge_config,
)


def test_openrouter_judge_defaults_use_openrouter_key(monkeypatch) -> None:
    """OpenRouter judge keeps DeepSeek-specific payload extras by default."""
    monkeypatch.setenv("JUDGE_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-secret")
    monkeypatch.delenv("JUDGE_API_URL", raising=False)
    monkeypatch.delenv("JUDGE_MODEL_NAME", raising=False)
    monkeypatch.delenv("JUDGE_API_KEY", raising=False)
    monkeypatch.delenv("JUDGE_EXTRA_PARAMS_JSON", raising=False)

    config = resolve_judge_config()
    headers = build_judge_headers(config)
    payload = build_judge_payload([{"role": "user", "content": "judge"}], config)

    assert config["provider"] == "openrouter"
    assert config["model_name"] == "deepseek/deepseek-r1"
    assert headers["Authorization"] == "Bearer openrouter-secret"
    assert headers["HTTP-Referer"] == "http://localhost"
    assert payload["temperature"] == 0.0
    assert payload["reasoning"] == {"effort": "none"}


def test_vllm_judge_omits_openrouter_headers_and_reasoning(monkeypatch) -> None:
    """Local Gemma/vLLM judge can run with no API key and no OpenRouter extras."""
    monkeypatch.setenv("JUDGE_PROVIDER", "vllm")
    monkeypatch.setenv("JUDGE_VLLM_API_URL", "http://127.0.0.1:18001/v1/chat/completions")
    monkeypatch.setenv("JUDGE_VLLM_MODEL_NAME", "gemma-4-26b-a4b")
    monkeypatch.delenv("JUDGE_API_URL", raising=False)
    monkeypatch.delenv("JUDGE_MODEL_NAME", raising=False)
    monkeypatch.delenv("JUDGE_API_KEY", raising=False)
    monkeypatch.delenv("JUDGE_EXTRA_PARAMS_JSON", raising=False)

    config = resolve_judge_config()
    headers = build_judge_headers(config)
    payload = build_judge_payload([{"role": "user", "content": "judge"}], config)

    assert config["provider"] == "vllm"
    assert config["api_url"] == "http://127.0.0.1:18001/v1/chat/completions"
    assert config["model_name"] == "gemma-4-26b-a4b"
    assert headers == {"Content-Type": "application/json"}
    assert payload["temperature"] == 0.0
    assert "reasoning" not in payload


def test_direct_local_judge_url_infers_vllm_provider(monkeypatch) -> None:
    """A non-OpenRouter JUDGE_API_URL is enough to select local-vLLM behavior."""
    monkeypatch.delenv("JUDGE_PROVIDER", raising=False)
    monkeypatch.delenv("JUDGE_BACKEND", raising=False)
    monkeypatch.setenv("JUDGE_API_URL", "http://localhost:18001/v1/chat/completions")
    monkeypatch.setenv("JUDGE_MODEL_NAME", "local-gemma")
    monkeypatch.delenv("JUDGE_API_KEY", raising=False)

    config = resolve_judge_config()
    metadata = judge_metadata(config)

    assert config["provider"] == "vllm"
    assert metadata["judge_model"] == "local-gemma"
    assert metadata["judge_temperature"] == 0.0


def test_judge_max_tokens_env_can_limit_output(monkeypatch) -> None:
    """JUDGE_MAX_TOKENS=48 should flow into judge payload and metadata."""
    monkeypatch.setenv("JUDGE_PROVIDER", "openrouter")
    monkeypatch.setenv("JUDGE_MODEL_NAME", "google/gemini-2.5-flash-lite")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-secret")
    monkeypatch.setenv("JUDGE_MAX_TOKENS", "48")
    monkeypatch.delenv("JUDGE_API_URL", raising=False)
    monkeypatch.delenv("JUDGE_API_KEY", raising=False)
    monkeypatch.delenv("JUDGE_EXTRA_PARAMS_JSON", raising=False)

    config = resolve_judge_config()
    payload = build_judge_payload([{"role": "user", "content": "judge"}], config)
    metadata = judge_metadata(config)

    assert config["max_tokens"] == 48
    assert payload["max_tokens"] == 48
    assert metadata["judge_max_tokens"] == 48
    assert payload["temperature"] == 0.0

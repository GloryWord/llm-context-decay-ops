"""Tests for request-header construction."""

import importlib

from src.utils.http_headers import build_json_headers, is_openrouter_url


def test_is_openrouter_url_matches_openrouter_host() -> None:
    assert is_openrouter_url("https://openrouter.ai/api/v1/chat/completions") is True
    assert is_openrouter_url("https://api.openrouter.ai/v1/chat/completions") is True
    assert is_openrouter_url("http://210.179.28.26:18000/v1/chat/completions") is False


def test_build_json_headers_skips_auth_for_vllm_without_key() -> None:
    headers = build_json_headers("http://210.179.28.26:18000/v1/chat/completions", "")

    assert headers == {"Content-Type": "application/json"}


def test_build_json_headers_supports_explicit_vllm_key() -> None:
    headers = build_json_headers(
        "http://210.179.28.26:18000/v1/chat/completions",
        "vllm-secret",
    )

    assert headers["Authorization"] == "Bearer vllm-secret"
    assert "HTTP-Referer" not in headers


def test_build_json_headers_adds_openrouter_metadata() -> None:
    headers = build_json_headers(
        "https://openrouter.ai/api/v1/chat/completions",
        "openrouter-secret",
    )

    assert headers["Authorization"] == "Bearer openrouter-secret"
    assert headers["HTTP-Referer"] == "http://localhost"


def test_run_experiment_uses_vllm_api_key_for_vllm(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-secret")
    monkeypatch.setenv("VLLM_API_KEY", "vllm-secret")
    monkeypatch.delenv("JUDGE_PROVIDER", raising=False)
    monkeypatch.delenv("JUDGE_BACKEND", raising=False)
    monkeypatch.delenv("JUDGE_API_URL", raising=False)
    monkeypatch.delenv("JUDGE_API_KEY", raising=False)

    import scripts.run_experiment as run_experiment

    run_experiment = importlib.reload(run_experiment)
    judge_config = run_experiment.resolve_judge_config()
    judge_headers = run_experiment.build_judge_headers(judge_config)

    assert run_experiment.MODEL_CONFIGS["vllm"]["api_key"] == "vllm-secret"
    assert run_experiment.MODEL_CONFIGS["deepseek-r1"]["api_key"] == "openrouter-secret"
    assert judge_headers["Authorization"] == "Bearer openrouter-secret"

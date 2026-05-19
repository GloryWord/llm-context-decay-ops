"""Unit tests for the vLLM readiness probe helper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "scripts" / "test_vllm_conn.py"
SPEC = importlib.util.spec_from_file_location("test_vllm_conn", MODULE_PATH)
assert SPEC and SPEC.loader
test_vllm_conn = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = test_vllm_conn
SPEC.loader.exec_module(test_vllm_conn)


def test_models_url_is_inferred_from_chat_completions_url() -> None:
    assert (
        test_vllm_conn.models_url_from_chat_url("http://host:8000/v1/chat/completions")
        == "http://host:8000/v1/models"
    )
    assert (
        test_vllm_conn.models_url_from_chat_url("http://host:8000/v1/chat/completions/")
        == "http://host:8000/v1/models"
    )


def test_extract_model_ids_ignores_malformed_entries() -> None:
    payload = {
        "data": [
            {"id": "model-a"},
            {"id": 7},
            "not-a-model",
            {"id": "model-b"},
        ]
    }

    assert test_vllm_conn.extract_model_ids(payload) == ["model-a", "model-b"]


def test_extract_completion_text_requires_non_empty_assistant_text() -> None:
    payload = {"choices": [{"message": {"content": "ready"}}]}

    assert test_vllm_conn.extract_completion_text(payload) == "ready"

    with pytest.raises(RuntimeError, match="empty content"):
        test_vllm_conn.extract_completion_text({"choices": [{"message": {"content": ""}}]})


def test_build_config_requires_api_url_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VLLM_API_URL", raising=False)
    monkeypatch.delenv("EVAL_MODEL_NAME", raising=False)

    args = test_vllm_conn.parse_args([])

    with pytest.raises(ValueError, match="VLLM API URL"):
        test_vllm_conn.build_config(args)


def test_build_config_uses_env_and_inferred_models_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VLLM_API_URL", "http://host:8000/v1/chat/completions")
    monkeypatch.setenv("EVAL_MODEL_NAME", "local-model")
    monkeypatch.delenv("VLLM_MODELS_URL", raising=False)

    config = test_vllm_conn.build_config(test_vllm_conn.parse_args([]))

    assert config.api_url == "http://host:8000/v1/chat/completions"
    assert config.model == "local-model"
    assert config.models_url == "http://host:8000/v1/models"

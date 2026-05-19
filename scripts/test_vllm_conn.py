"""Readiness probe for OpenAI-compatible vLLM chat endpoints.

The orchestration scripts use this as a stronger readiness gate than
``/v1/models`` alone: the expected model must be listed and a tiny
chat-completion request must return non-empty text.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.http_headers import build_json_headers

load_dotenv(ROOT / ".env")


DEFAULT_PROMPT = "준비 상태 확인용으로 한 단어만 답하세요."


@dataclass(frozen=True)
class ReadinessConfig:
    api_url: str
    model: str
    api_key: str
    models_url: str
    prompt: str = DEFAULT_PROMPT
    max_tokens: int = 8
    timeout_seconds: float = 20.0
    skip_models: bool = False


def models_url_from_chat_url(api_url: str) -> str:
    """Infer the OpenAI-compatible models URL from a chat-completions URL."""
    trimmed = api_url.rstrip("/")
    suffix = "/chat/completions"
    if trimmed.endswith(suffix):
        return trimmed[: -len(suffix)] + "/models"
    return trimmed + "/models"


def extract_model_ids(models_payload: dict[str, Any]) -> list[str]:
    """Extract model IDs from an OpenAI-compatible ``/v1/models`` payload."""
    data = models_payload.get("data", [])
    if not isinstance(data, list):
        return []
    ids: list[str] = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            ids.append(item["id"])
    return ids


def extract_completion_text(completion_payload: dict[str, Any]) -> str:
    """Extract assistant text from a chat-completion payload."""
    choices = completion_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError(f"completion response has no choices: {completion_payload!r}")
    first = choices[0]
    if not isinstance(first, dict):
        raise RuntimeError(f"completion choice is not an object: {first!r}")
    message = first.get("message")
    if not isinstance(message, dict):
        raise RuntimeError(f"completion choice has no message object: {first!r}")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"completion message has empty content: {first!r}")
    return content


def build_config(args: argparse.Namespace) -> ReadinessConfig:
    """Build a validated readiness config from CLI args and environment."""
    api_url = args.api_url or os.getenv("VLLM_API_URL")
    model = args.model or os.getenv("EVAL_MODEL_NAME")
    api_key = args.api_key if args.api_key is not None else os.getenv("VLLM_API_KEY", "")

    if not api_url:
        raise ValueError("VLLM API URL is required (--api-url or VLLM_API_URL)")
    if not model:
        raise ValueError("Model name is required (--model or EVAL_MODEL_NAME)")

    models_url = args.models_url or os.getenv("VLLM_MODELS_URL") or models_url_from_chat_url(api_url)
    return ReadinessConfig(
        api_url=api_url,
        model=model,
        api_key=api_key,
        models_url=models_url,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        timeout_seconds=args.timeout,
        skip_models=args.skip_models,
    )


async def _json_request(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    *,
    label: str,
    headers: dict[str, str] | None = None,
    json_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async with session.request(method, url, headers=headers, json=json_payload) as resp:
        text = await resp.text()
        if resp.status != 200:
            raise RuntimeError(f"{label} returned HTTP {resp.status}: {text[:500]}")
        try:
            parsed = await resp.json(content_type=None)
        except Exception as exc:  # pragma: no cover - defensive detail path
            raise RuntimeError(f"{label} returned non-JSON body: {text[:500]}") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError(f"{label} returned non-object JSON: {parsed!r}")
        return parsed


async def check_models_endpoint(
    session: aiohttp.ClientSession,
    config: ReadinessConfig,
) -> list[str]:
    """Verify the expected model is visible from ``/v1/models``."""
    payload = await _json_request(session, "GET", config.models_url, label="/v1/models")
    model_ids = extract_model_ids(payload)
    if config.model not in model_ids:
        raise RuntimeError(
            f"expected model {config.model!r} not listed by {config.models_url}; "
            f"available={model_ids}"
        )
    return model_ids


async def check_chat_completion(
    session: aiohttp.ClientSession,
    config: ReadinessConfig,
) -> str:
    """Verify the chat-completions endpoint can generate with the expected model."""
    headers = build_json_headers(config.api_url, config.api_key)
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": config.prompt}],
        "temperature": 0.0,
        "max_tokens": config.max_tokens,
    }
    completion = await _json_request(
        session,
        "POST",
        config.api_url,
        label="/v1/chat/completions",
        headers=headers,
        json_payload=payload,
    )
    return extract_completion_text(completion)


async def probe_readiness(config: ReadinessConfig) -> dict[str, Any]:
    """Run the full readiness probe and return structured evidence."""
    timeout = aiohttp.ClientTimeout(total=config.timeout_seconds, connect=min(5.0, config.timeout_seconds))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        model_ids: list[str] = []
        if not config.skip_models:
            model_ids = await check_models_endpoint(session, config)
        completion_text = await check_chat_completion(session, config)
    return {
        "api_url": config.api_url,
        "models_url": config.models_url,
        "model": config.model,
        "model_ids": model_ids,
        "completion_preview": completion_text[:120],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe vLLM chat-completion readiness.")
    parser.add_argument("--api-url", default=None, help="Chat-completions URL; defaults to VLLM_API_URL.")
    parser.add_argument("--models-url", default=None, help="Models URL; defaults to VLLM_MODELS_URL or inferred.")
    parser.add_argument("--model", default=None, help="Expected model name; defaults to EVAL_MODEL_NAME.")
    parser.add_argument(
        "--api-key",
        default=None,
        help="Optional bearer token; defaults to VLLM_API_KEY when omitted.",
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--max-tokens", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument(
        "--skip-models",
        action="store_true",
        help="Skip /v1/models and only probe chat completions.",
    )
    parser.add_argument("--quiet", action="store_true", help="Print only PASS/FAIL summary.")
    return parser.parse_args(argv)


async def test_inference(config: ReadinessConfig | None = None) -> dict[str, Any]:
    """Backward-compatible async entry point for readiness probing."""
    if config is None:
        config = build_config(parse_args([]))
    return await probe_readiness(config)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = build_config(args)
        evidence = asyncio.run(probe_readiness(config))
    except Exception as exc:
        print(f"[FAIL] vLLM readiness probe failed: {exc}", file=sys.stderr)
        return 1

    if args.quiet:
        print(f"[PASS] vLLM ready: model={evidence['model']} url={evidence['api_url']}")
    else:
        print("[PASS] vLLM readiness probe succeeded")
        print(f"URL: {evidence['api_url']}")
        print(f"Models URL: {evidence['models_url']}")
        print(f"Model: {evidence['model']}")
        print("\n[Inference Result]")
        print(evidence["completion_preview"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

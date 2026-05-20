"""Helpers for building request headers for inference APIs."""

from urllib.parse import urlparse


def is_openrouter_url(api_url: str) -> bool:
    """Return True when the target URL points at OpenRouter."""
    hostname = (urlparse(api_url).hostname or "").lower()
    return hostname == "openrouter.ai" or hostname.endswith(".openrouter.ai")


def build_json_headers(api_url: str, api_key: str = "") -> dict[str, str]:
    """Build JSON request headers without leaking unrelated bearer tokens."""
    headers = {"Content-Type": "application/json"}

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if is_openrouter_url(api_url):
        headers["HTTP-Referer"] = "http://localhost"

    return headers

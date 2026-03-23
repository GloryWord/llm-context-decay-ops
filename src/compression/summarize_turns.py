"""LLM-based turn summarization compression.

Uses a cheap model via OpenRouter to summarize each intermediate turn
into a concise single sentence. System prompt is never modified.
"""

import asyncio
import logging
import os

import aiohttp

from src.compression.base import BaseCompressor
from src.data_pipeline.token_utils import count_tokens

logger = logging.getLogger(__name__)

API_URL = "https://openrouter.ai/api/v1/chat/completions"

SUMMARIZE_PROMPT = (
    "Summarize the following message in one concise sentence. "
    "Preserve key information and intent. Output ONLY the summary, nothing else.\n\n"
    "Message: {content}"
)


class SummarizeTurnsCompressor(BaseCompressor):
    """Summarize each intermediate turn using an LLM."""

    @property
    def method_name(self) -> str:
        return "summarize_turns"

    def compress(
        self,
        system_prompt: str,
        intermediate_turns: list[dict],
        params: dict,
    ) -> tuple[list[dict], dict]:
        """Summarize each turn via LLM API call.

        This is a sync wrapper around the async implementation.
        Must be called from a context where asyncio.run() is safe,
        or use compress_async() directly.

        Args:
            system_prompt: System prompt (read-only context).
            intermediate_turns: Original turns.
            params: Must contain 'model', 'max_summary_tokens', 'temperature'.

        Returns:
            Tuple of (summarized_turns, metadata).
        """
        if not intermediate_turns:
            return [], {
                "original_token_count": 0,
                "compressed_token_count": 0,
                "compression_ratio": 1.0,
            }

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already inside an event loop; create a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self.compress_async(system_prompt, intermediate_turns, params),
                )
                return future.result()
        else:
            return asyncio.run(
                self.compress_async(system_prompt, intermediate_turns, params)
            )

    async def compress_async(
        self,
        system_prompt: str,
        intermediate_turns: list[dict],
        params: dict,
    ) -> tuple[list[dict], dict]:
        """Async implementation of turn summarization.

        Args:
            system_prompt: System prompt (read-only).
            intermediate_turns: Original turns.
            params: Method parameters.

        Returns:
            Tuple of (summarized_turns, metadata).
        """
        model = params.get("model", "google/gemini-2.0-flash-lite")
        max_tokens = params.get("max_summary_tokens", 50)
        temperature = params.get("temperature", 0.0)
        batch_size = params.get("batch_size", 10)

        original_text = " ".join(t["content"] for t in intermediate_turns)
        original_tokens = count_tokens(original_text)

        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            logger.error("OPENROUTER_API_KEY not set; returning original turns")
            return list(intermediate_turns), {
                "original_token_count": original_tokens,
                "compressed_token_count": original_tokens,
                "compression_ratio": 1.0,
            }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost",
            "Content-Type": "application/json",
        }

        compressed_turns: list[dict] = []

        async with aiohttp.ClientSession() as session:
            # Process in batches to respect rate limits
            for i in range(0, len(intermediate_turns), batch_size):
                batch = intermediate_turns[i:i + batch_size]
                tasks = [
                    _summarize_turn(session, headers, turn, model, max_tokens, temperature)
                    for turn in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for turn, result in zip(batch, results):
                    if isinstance(result, Exception):
                        logger.warning("Summarization failed for turn, keeping original: %s", result)
                        compressed_turns.append(dict(turn))
                    else:
                        compressed_turns.append(result)

        compressed_text = " ".join(t["content"] for t in compressed_turns)
        compressed_tokens = count_tokens(compressed_text)
        ratio = compressed_tokens / original_tokens if original_tokens > 0 else 1.0

        metadata = {
            "original_token_count": original_tokens,
            "compressed_token_count": compressed_tokens,
            "compression_ratio": round(ratio, 4),
        }

        logger.info(
            "SummarizeTurns: %d -> %d tokens (ratio=%.4f), %d turns",
            original_tokens, compressed_tokens, ratio, len(compressed_turns),
        )

        return compressed_turns, metadata


async def _summarize_turn(
    session: aiohttp.ClientSession,
    headers: dict,
    turn: dict,
    model: str,
    max_tokens: int,
    temperature: float,
) -> dict:
    """Summarize a single turn via API call.

    Args:
        session: aiohttp session.
        headers: Request headers with auth.
        turn: Original turn dict.
        model: Model identifier.
        max_tokens: Max tokens for summary.
        temperature: Sampling temperature.

    Returns:
        Summarized turn dict with same role.
    """
    content = turn["content"]

    # Skip very short turns (not worth summarizing)
    if count_tokens(content) <= max_tokens:
        return dict(turn)

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": SUMMARIZE_PROMPT.format(content=content)},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with session.post(API_URL, headers=headers, json=payload) as resp:
                if resp.status == 429:
                    wait = 2 ** attempt
                    logger.warning("Rate limited, waiting %ds", wait)
                    await asyncio.sleep(wait)
                    continue

                result = await resp.json()

                if "choices" in result and result["choices"]:
                    summary = result["choices"][0]["message"]["content"].strip()
                    return {"role": turn["role"], "content": summary}
                else:
                    logger.warning("Unexpected API response: %s", result)
                    return dict(turn)

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning("API call failed (attempt %d): %s", attempt + 1, e)
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)

    # All retries failed, return original
    return dict(turn)

"""Sliding window compression: keep only the last N turns.

System prompt is always preserved (handled externally).
This is the simplest baseline compression method.
"""

import logging

from src.compression.base import BaseCompressor
from src.data_pipeline.token_utils import count_tokens

logger = logging.getLogger(__name__)


class SlidingWindowCompressor(BaseCompressor):
    """Keep only the most recent N turns from intermediate conversation."""

    @property
    def method_name(self) -> str:
        return "sliding_window"

    def compress(
        self,
        system_prompt: str,
        intermediate_turns: list[dict],
        params: dict,
    ) -> tuple[list[dict], dict]:
        """Keep the last window_size turns.

        Args:
            system_prompt: System prompt (read-only context).
            intermediate_turns: Original turns.
            params: Must contain 'window_size' (int).

        Returns:
            Tuple of (windowed_turns, metadata).
        """
        window_size = params["window_size"]

        original_text = " ".join(t["content"] for t in intermediate_turns)
        original_tokens = count_tokens(original_text)

        if len(intermediate_turns) <= window_size:
            compressed = list(intermediate_turns)
        else:
            compressed = intermediate_turns[-window_size:]

        compressed_text = " ".join(t["content"] for t in compressed)
        compressed_tokens = count_tokens(compressed_text)

        ratio = compressed_tokens / original_tokens if original_tokens > 0 else 1.0

        metadata = {
            "original_token_count": original_tokens,
            "compressed_token_count": compressed_tokens,
            "compression_ratio": round(ratio, 4),
        }

        logger.debug(
            "SlidingWindow(size=%d): %d turns -> %d turns, ratio=%.4f",
            window_size, len(intermediate_turns), len(compressed), ratio,
        )

        return compressed, metadata

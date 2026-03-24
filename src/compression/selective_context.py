"""Selective context compression: token-level pruning by self-information.

Removes low-information tokens from intermediate turns while preserving
high-information content. Based on Li et al., 2023 "Compressing Context
to Enhance Inference Efficiency of Large Language Models."

System prompt is never pruned.
"""

import logging
import math

from src.compression.base import BaseCompressor
from src.data_pipeline.token_utils import count_tokens, get_tokenizer

logger = logging.getLogger(__name__)


class SelectiveContextCompressor(BaseCompressor):
    """Prune low-information tokens from intermediate turns."""

    @property
    def method_name(self) -> str:
        return "selective_context"

    def compress(
        self,
        system_prompt: str,
        intermediate_turns: list[dict],
        params: dict,
    ) -> tuple[list[dict], dict]:
        """Prune tokens below self-information threshold.

        Args:
            system_prompt: System prompt (read-only context).
            intermediate_turns: Original turns.
            params: Must contain 'target_ratio' (float, 0-1).

        Returns:
            Tuple of (pruned_turns, metadata).
        """
        target_ratio = params["target_ratio"]
        model_name = params.get("model_name", "Qwen/Qwen3.5-9B")

        original_text = " ".join(t["content"] for t in intermediate_turns)
        original_tokens = count_tokens(original_text, model_name)

        if not intermediate_turns or original_tokens == 0:
            return list(intermediate_turns), {
                "original_token_count": 0,
                "compressed_token_count": 0,
                "compression_ratio": 1.0,
            }

        enc = get_tokenizer(model_name)
        compressed_turns = []

        for turn in intermediate_turns:
            content = turn["content"]
            pruned_content = _prune_content(content, target_ratio, enc)
            compressed_turns.append({
                "role": turn["role"],
                "content": pruned_content,
            })

        compressed_text = " ".join(t["content"] for t in compressed_turns)
        compressed_tokens = count_tokens(compressed_text, model_name)
        ratio = compressed_tokens / original_tokens if original_tokens > 0 else 1.0

        metadata = {
            "original_token_count": original_tokens,
            "compressed_token_count": compressed_tokens,
            "compression_ratio": round(ratio, 4),
        }

        logger.debug(
            "SelectiveContext(ratio=%.2f): %d -> %d tokens, actual_ratio=%.4f",
            target_ratio, original_tokens, compressed_tokens, ratio,
        )

        return compressed_turns, metadata


def _prune_content(text: str, target_ratio: float, enc: object) -> str:
    """Prune low-information words from text to meet target ratio.

    Uses word-level self-information approximation: shorter, more common
    words (articles, prepositions, filler) get lower scores. Words are
    ranked by information score and the lowest-scoring ones are removed.

    Args:
        text: Input text content.
        target_ratio: Target fraction of tokens to retain.
        enc: Tokenizer instance (HuggingFace PreTrainedTokenizer).

    Returns:
        Pruned text string.
    """
    words = text.split()
    if len(words) <= 2:
        return text

    # Compute self-information proxy per word:
    # token count per word serves as information proxy —
    # common short words (a, the, is) = 1 token = low info,
    # rare/long words = multiple tokens = high info
    scored: list[tuple[int, float, str]] = []
    for idx, word in enumerate(words):
        token_count = len(enc.encode(word))
        # Penalize very common short words more aggressively
        char_len = len(word.strip(".,!?;:\"'()[]{}"))
        info_score = token_count + (char_len / 10.0)
        scored.append((idx, info_score, word))

    # Sort by info score ascending (lowest info first)
    scored_sorted = sorted(scored, key=lambda x: x[1])

    # Calculate how many words to remove
    target_word_count = max(1, int(len(words) * target_ratio))
    words_to_remove = len(words) - target_word_count

    # Mark lowest-info words for removal
    remove_indices: set[int] = set()
    for i in range(min(words_to_remove, len(scored_sorted))):
        remove_indices.add(scored_sorted[i][0])

    # Rebuild text preserving word order
    pruned = [w for idx, w in enumerate(words) if idx not in remove_indices]
    return " ".join(pruned) if pruned else words[0]

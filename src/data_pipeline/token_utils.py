"""Token counting utilities using Qwen BPE tokenizer.

Provides shared helpers for measuring text length in tokens,
used across all preprocessing modules.

v2: Replaced tiktoken cl100k_base with HuggingFace AutoTokenizer
for Qwen/Qwen3.5-9B to match the target model's BPE vocabulary.
"""

import logging
import os

# Prevent HuggingFace tokenizer Rust core deadlock under concurrency
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from transformers import AutoTokenizer, PreTrainedTokenizerBase  # noqa: E402

logger = logging.getLogger(__name__)

# Default model for tokenization — must match the inference target model
DEFAULT_MODEL_NAME = "Qwen/Qwen3.5-9B"
FALLBACK_MODEL_NAME = "Qwen/Qwen2.5-7B"

# Module-level singleton cache
_tokenizer_cache: dict[str, PreTrainedTokenizerBase] = {}


def get_tokenizer(model_name: str = DEFAULT_MODEL_NAME) -> PreTrainedTokenizerBase:
    """Get a cached HuggingFace tokenizer instance.

    Args:
        model_name: HuggingFace model ID for the tokenizer.

    Returns:
        The tokenizer instance.
    """
    if model_name not in _tokenizer_cache:
        try:
            _tokenizer_cache[model_name] = AutoTokenizer.from_pretrained(model_name)
            logger.info("Loaded tokenizer: %s", model_name)
        except Exception:
            logger.warning(
                "Failed to load tokenizer %s, falling back to %s",
                model_name, FALLBACK_MODEL_NAME,
            )
            if FALLBACK_MODEL_NAME not in _tokenizer_cache:
                _tokenizer_cache[FALLBACK_MODEL_NAME] = AutoTokenizer.from_pretrained(
                    FALLBACK_MODEL_NAME
                )
            _tokenizer_cache[model_name] = _tokenizer_cache[FALLBACK_MODEL_NAME]
    return _tokenizer_cache[model_name]


def count_tokens(text: str, model_name: str = DEFAULT_MODEL_NAME) -> int:
    """Count the number of tokens in a text string.

    Args:
        text: The text to tokenize.
        model_name: HuggingFace model ID for the tokenizer.

    Returns:
        Number of tokens.
    """
    tokenizer = get_tokenizer(model_name)
    return len(tokenizer.encode(text))


def is_in_token_range(
    text: str,
    min_tokens: int,
    max_tokens: int,
    model_name: str = DEFAULT_MODEL_NAME,
) -> bool:
    """Check if text token count falls within [min_tokens, max_tokens].

    Args:
        text: The text to check.
        min_tokens: Minimum token count (inclusive).
        max_tokens: Maximum token count (inclusive).
        model_name: HuggingFace model ID for the tokenizer.

    Returns:
        True if token count is within the specified range.
    """
    n = count_tokens(text, model_name)
    return min_tokens <= n <= max_tokens

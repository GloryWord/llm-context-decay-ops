"""Token counting utilities using tiktoken.

Provides shared helpers for measuring text length in tokens,
used across all preprocessing modules.
"""

import tiktoken

# Module-level cache for encoding instances
_encoding_cache: dict[str, tiktoken.Encoding] = {}


def get_encoding(encoding_name: str = "cl100k_base") -> tiktoken.Encoding:
    """Get a cached tiktoken encoding instance.

    Args:
        encoding_name: Name of the tiktoken encoding to use.

    Returns:
        The tiktoken Encoding object.
    """
    if encoding_name not in _encoding_cache:
        _encoding_cache[encoding_name] = tiktoken.get_encoding(encoding_name)
    return _encoding_cache[encoding_name]


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count the number of tokens in a text string.

    Args:
        text: The text to tokenize.
        encoding_name: Name of the tiktoken encoding.

    Returns:
        Number of tokens.
    """
    enc = get_encoding(encoding_name)
    return len(enc.encode(text))


def is_in_token_range(
    text: str,
    min_tokens: int,
    max_tokens: int,
    encoding_name: str = "cl100k_base",
) -> bool:
    """Check if text token count falls within [min_tokens, max_tokens].

    Args:
        text: The text to check.
        min_tokens: Minimum token count (inclusive).
        max_tokens: Maximum token count (inclusive).
        encoding_name: Name of the tiktoken encoding.

    Returns:
        True if token count is within the specified range.
    """
    n = count_tokens(text, encoding_name)
    return min_tokens <= n <= max_tokens

"""Abstract base class for context compression methods.

All compressors operate on intermediate turns only.
System prompt and probe turn are never modified.
"""

from abc import ABC, abstractmethod


class BaseCompressor(ABC):
    """Abstract base for all compression methods.

    Subclasses must implement compress() and method_name.
    The contract: system_prompt and probe_turn are read-only context;
    only intermediate_turns are transformed.
    """

    @abstractmethod
    def compress(
        self,
        system_prompt: str,
        intermediate_turns: list[dict],
        params: dict,
    ) -> tuple[list[dict], dict]:
        """Compress intermediate turns.

        Args:
            system_prompt: The system prompt (read-only, for context).
            intermediate_turns: Original turn list [{role, content}, ...].
            params: Method-specific parameters from config.

        Returns:
            Tuple of (compressed_turns, metadata_dict).
            metadata_dict must contain:
                - original_token_count: int
                - compressed_token_count: int
                - compression_ratio: float
        """
        ...

    @property
    @abstractmethod
    def method_name(self) -> str:
        """Unique identifier for this compression method."""
        ...

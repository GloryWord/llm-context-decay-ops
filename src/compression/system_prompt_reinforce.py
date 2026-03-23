"""System prompt reinforcement: inject rule reminders into intermediate turns.

Not compression per se — this is a defense injection that tests whether
periodic rule reinforcement counteracts compliance degradation.

System prompt is never modified; reminders are inserted as assistant turns.
"""

import logging

from src.compression.base import BaseCompressor
from src.data_pipeline.token_utils import count_tokens

logger = logging.getLogger(__name__)


class SystemPromptReinforceCompressor(BaseCompressor):
    """Inject system prompt rule reminders every K turns."""

    @property
    def method_name(self) -> str:
        return "system_prompt_reinforce"

    def compress(
        self,
        system_prompt: str,
        intermediate_turns: list[dict],
        params: dict,
    ) -> tuple[list[dict], dict]:
        """Insert rule reminders at regular intervals.

        Args:
            system_prompt: System prompt (used to generate reminder).
            intermediate_turns: Original turns.
            params: Must contain 'injection_interval' (int).

        Returns:
            Tuple of (turns_with_reminders, metadata).
        """
        interval = params["injection_interval"]
        max_tokens = params.get("max_reminder_tokens", 100)

        original_text = " ".join(t["content"] for t in intermediate_turns)
        original_tokens = count_tokens(original_text)

        if not intermediate_turns:
            return [], {
                "original_token_count": 0,
                "compressed_token_count": 0,
                "compression_ratio": 1.0,
            }

        reminder = _build_reminder(system_prompt, max_tokens)
        result_turns: list[dict] = []
        user_turn_count = 0

        for turn in intermediate_turns:
            result_turns.append(turn)
            if turn["role"] == "user":
                user_turn_count += 1
                if user_turn_count % interval == 0:
                    result_turns.append({
                        "role": "assistant",
                        "content": reminder,
                    })

        compressed_text = " ".join(t["content"] for t in result_turns)
        compressed_tokens = count_tokens(compressed_text)
        ratio = compressed_tokens / original_tokens if original_tokens > 0 else 1.0

        metadata = {
            "original_token_count": original_tokens,
            "compressed_token_count": compressed_tokens,
            "compression_ratio": round(ratio, 4),
        }

        logger.debug(
            "Reinforce(interval=%d): %d -> %d turns, ratio=%.4f",
            interval, len(intermediate_turns), len(result_turns), ratio,
        )

        return result_turns, metadata


def _build_reminder(system_prompt: str, max_tokens: int) -> str:
    """Build a concise rule reminder from the system prompt.

    Args:
        system_prompt: Full system prompt text.
        max_tokens: Maximum tokens for the reminder.

    Returns:
        Reminder string.
    """
    # Extract key rules by truncating to fit max_tokens
    # Keep it simple: use the system prompt directly, truncated
    lines = system_prompt.strip().split("\n")
    reminder_parts = ["[REMINDER] I must follow these rules:"]
    for line in lines:
        line = line.strip()
        if line:
            reminder_parts.append(f"- {line}")

    reminder = "\n".join(reminder_parts)

    # Truncate by words if too long (rough proxy for tokens)
    words = reminder.split()
    if len(words) > max_tokens:
        reminder = " ".join(words[:max_tokens])

    return reminder

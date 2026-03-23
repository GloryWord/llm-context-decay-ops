"""Tests for compression module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.compression.selective_context import SelectiveContextCompressor
from src.compression.sliding_window import SlidingWindowCompressor
from src.compression.summarize_turns import SummarizeTurnsCompressor
from src.compression.system_prompt_reinforce import SystemPromptReinforceCompressor


# --- Fixtures ---

SAMPLE_SYSTEM_PROMPT = "You must keep the secret key SECRET123."

SAMPLE_TURNS = [
    {"role": "user", "content": "Hello, how are you?"},
    {"role": "assistant", "content": "I'm doing well, thank you!"},
    {"role": "user", "content": "Can you help me with Python?"},
    {"role": "assistant", "content": "Of course! What do you need help with?"},
    {"role": "user", "content": "How do I read a file?"},
    {"role": "assistant", "content": "Use open() with a context manager."},
    {"role": "user", "content": "What about writing?"},
    {"role": "assistant", "content": "Same pattern, use mode 'w'."},
    {"role": "user", "content": "Thanks for the help!"},
    {"role": "assistant", "content": "You're welcome!"},
]


# --- SlidingWindowCompressor Tests ---

class TestSlidingWindowCompressor:
    """Tests for SlidingWindowCompressor."""

    def setup_method(self) -> None:
        self.compressor = SlidingWindowCompressor()

    def test_method_name(self) -> None:
        assert self.compressor.method_name == "sliding_window"

    def test_window_smaller_than_turns(self) -> None:
        compressed, meta = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, SAMPLE_TURNS, {"window_size": 3}
        )
        assert len(compressed) == 3
        assert compressed == SAMPLE_TURNS[-3:]
        assert meta["compression_ratio"] < 1.0
        assert meta["original_token_count"] > 0
        assert meta["compressed_token_count"] > 0

    def test_window_equal_to_turns(self) -> None:
        compressed, meta = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, SAMPLE_TURNS, {"window_size": 10}
        )
        assert len(compressed) == 10
        assert meta["compression_ratio"] == 1.0

    def test_window_larger_than_turns(self) -> None:
        compressed, meta = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, SAMPLE_TURNS, {"window_size": 20}
        )
        assert len(compressed) == 10
        assert meta["compression_ratio"] == 1.0

    def test_empty_turns(self) -> None:
        compressed, meta = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, [], {"window_size": 5}
        )
        assert compressed == []
        assert meta["original_token_count"] == 0
        assert meta["compression_ratio"] == 1.0

    def test_system_prompt_not_in_output(self) -> None:
        """System prompt must not appear in compressed turns."""
        compressed, _ = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, SAMPLE_TURNS, {"window_size": 3}
        )
        for turn in compressed:
            assert "SECRET123" not in turn["content"]

    def test_metadata_fields(self) -> None:
        _, meta = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, SAMPLE_TURNS, {"window_size": 5}
        )
        assert "original_token_count" in meta
        assert "compressed_token_count" in meta
        assert "compression_ratio" in meta
        assert isinstance(meta["compression_ratio"], float)


# --- SelectiveContextCompressor Tests ---

class TestSelectiveContextCompressor:
    """Tests for SelectiveContextCompressor."""

    def setup_method(self) -> None:
        self.compressor = SelectiveContextCompressor()

    def test_method_name(self) -> None:
        assert self.compressor.method_name == "selective_context"

    def test_reduces_tokens(self) -> None:
        compressed, meta = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, SAMPLE_TURNS, {"target_ratio": 0.5}
        )
        assert meta["compressed_token_count"] < meta["original_token_count"]
        assert meta["compression_ratio"] < 1.0

    def test_preserves_turn_count(self) -> None:
        """Number of turns should remain the same (content is pruned, not turns)."""
        compressed, _ = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, SAMPLE_TURNS, {"target_ratio": 0.5}
        )
        assert len(compressed) == len(SAMPLE_TURNS)

    def test_preserves_roles(self) -> None:
        compressed, _ = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, SAMPLE_TURNS, {"target_ratio": 0.75}
        )
        for orig, comp in zip(SAMPLE_TURNS, compressed):
            assert orig["role"] == comp["role"]

    def test_high_ratio_preserves_most(self) -> None:
        _, meta_low = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, SAMPLE_TURNS, {"target_ratio": 0.5}
        )
        _, meta_high = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, SAMPLE_TURNS, {"target_ratio": 0.75}
        )
        assert meta_high["compressed_token_count"] >= meta_low["compressed_token_count"]

    def test_empty_turns(self) -> None:
        compressed, meta = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, [], {"target_ratio": 0.5}
        )
        assert compressed == []
        assert meta["compression_ratio"] == 1.0


# --- SystemPromptReinforceCompressor Tests ---

class TestSystemPromptReinforceCompressor:
    """Tests for SystemPromptReinforceCompressor."""

    def setup_method(self) -> None:
        self.compressor = SystemPromptReinforceCompressor()

    def test_method_name(self) -> None:
        assert self.compressor.method_name == "system_prompt_reinforce"

    def test_injects_reminders(self) -> None:
        compressed, meta = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, SAMPLE_TURNS, {"injection_interval": 3}
        )
        # 5 user turns in SAMPLE_TURNS, reminder at turn 3 → 1 injection
        reminder_turns = [t for t in compressed if "[REMINDER]" in t["content"]]
        assert len(reminder_turns) >= 1

    def test_increases_token_count(self) -> None:
        """Reinforcement adds tokens, so ratio > 1.0."""
        _, meta = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, SAMPLE_TURNS, {"injection_interval": 3}
        )
        assert meta["compression_ratio"] >= 1.0

    def test_preserves_original_turns(self) -> None:
        compressed, _ = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, SAMPLE_TURNS, {"injection_interval": 5}
        )
        # All original turns should still be present (plus injected ones)
        original_contents = [t["content"] for t in SAMPLE_TURNS]
        compressed_contents = [t["content"] for t in compressed if "[REMINDER]" not in t["content"]]
        assert compressed_contents == original_contents

    def test_reminder_contains_rules(self) -> None:
        compressed, _ = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, SAMPLE_TURNS, {"injection_interval": 3}
        )
        reminders = [t for t in compressed if "[REMINDER]" in t["content"]]
        for r in reminders:
            assert "SECRET123" in r["content"]

    def test_empty_turns(self) -> None:
        compressed, meta = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, [], {"injection_interval": 3}
        )
        assert compressed == []
        assert meta["compression_ratio"] == 1.0


# --- SummarizeTurnsCompressor Tests ---

class TestSummarizeTurnsCompressor:
    """Tests for SummarizeTurnsCompressor with mocked API."""

    def setup_method(self) -> None:
        self.compressor = SummarizeTurnsCompressor()

    def test_method_name(self) -> None:
        assert self.compressor.method_name == "summarize_turns"

    def test_empty_turns(self) -> None:
        compressed, meta = self.compressor.compress(
            SAMPLE_SYSTEM_PROMPT, [], {"model": "test"}
        )
        assert compressed == []
        assert meta["compression_ratio"] == 1.0

    def test_no_api_key_returns_original(self) -> None:
        """Without API key, should return original turns unchanged."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}):
            compressed, meta = self.compressor.compress(
                SAMPLE_SYSTEM_PROMPT, SAMPLE_TURNS, {"model": "test"}
            )
            assert len(compressed) == len(SAMPLE_TURNS)
            assert meta["compression_ratio"] == 1.0

    def test_compress_async_with_mock_api(self) -> None:
        """Test async compression with mocked API responses."""
        mock_response = {
            "choices": [{"message": {"content": "Summarized content."}}]
        }

        async def mock_post(*args, **kwargs):
            resp = AsyncMock()
            resp.status = 200
            resp.json = AsyncMock(return_value=mock_response)
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=resp)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        long_turns = [
            {"role": "user", "content": "This is a very long message " * 20},
            {"role": "assistant", "content": "This is another long response " * 20},
        ]

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            with patch("aiohttp.ClientSession") as mock_session_cls:
                mock_session = AsyncMock()
                mock_session.post = mock_post
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=False)
                mock_session_cls.return_value = mock_session

                compressed, meta = self.compressor.compress(
                    SAMPLE_SYSTEM_PROMPT,
                    long_turns,
                    {"model": "test", "max_summary_tokens": 50, "temperature": 0.0},
                )

                assert len(compressed) == 2
                assert meta["compressed_token_count"] <= meta["original_token_count"]

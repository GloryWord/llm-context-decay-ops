"""Preprocess ShareGPT dataset for Phase 1 experiments.

Extracts user ("human") messages from ShareGPT conversations,
applies quality filters, classifies by token length bin,
and outputs turns for use as intermediate conversation padding.

Usage:
    python -m src.data_pipeline.preprocess_sharegpt --config configs/preprocess.yaml
"""

import argparse
import json
import logging
import re
from pathlib import Path

import yaml

from src.data_pipeline.token_utils import count_tokens, is_in_token_range

logger = logging.getLogger(__name__)


def is_english(text: str) -> bool:
    """Heuristic check: text is predominantly English.

    Args:
        text: Input text to check.

    Returns:
        True if text appears to be English (>70% ASCII letters).
    """
    if not text:
        return False
    ascii_letters = sum(1 for c in text if c.isascii() and c.isalpha())
    total_letters = sum(1 for c in text if c.isalpha())
    if total_letters == 0:
        return False
    return (ascii_letters / total_letters) > 0.7


def passes_quality_filter(text: str, filters: dict) -> bool:
    """Check if text passes all quality filters.

    Args:
        text: Input text to check.
        filters: Quality filter config dict.

    Returns:
        True if text passes all filters.
    """
    # Minimum length
    if len(text) < filters.get("min_length_chars", 10):
        return False

    # Language check
    if filters.get("language") == "en" and not is_english(text):
        return False

    # Exclude patterns
    text_lower = text.lower()
    for pattern in filters.get("exclude_patterns", []):
        if pattern.lower() in text_lower:
            return False

    return True


def preprocess_sharegpt(config_path: str) -> dict[str, list[dict]]:
    """Run full ShareGPT preprocessing pipeline.

    Args:
        config_path: Path to preprocess.yaml.

    Returns:
        Dict mapping bin names to lists of turn records.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    raw_dir = Path(cfg["paths"]["raw_dir"])
    processed_dir = Path(cfg["paths"]["processed_dir"])
    sharegpt_cfg = cfg["sharegpt_preprocess"]
    tokenizer_cfg = cfg["tokenizer"]

    model_name = tokenizer_cfg.get("model_name", "Qwen/Qwen3.5-9B")
    bins = sharegpt_cfg["token_length_bins"]
    quality_filters = sharegpt_cfg["quality_filters"]
    max_per_bin = sharegpt_cfg.get("max_turns_per_bin", 100)

    # Find the downloaded ShareGPT file
    sharegpt_dir = raw_dir / cfg["datasets"]["sharegpt"]["raw_subdir"]
    sharegpt_file = sharegpt_dir / cfg["datasets"]["sharegpt"]["hf_filename"]
    if not sharegpt_file.exists():
        logger.error("ShareGPT data not found at %s", sharegpt_file)
        return {}

    logger.info("Loading ShareGPT from %s ...", sharegpt_file)
    with open(sharegpt_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # Collect turns by bin
    binned_turns: dict[str, list[dict]] = {bin_name: [] for bin_name in bins}
    total_extracted = 0
    total_filtered = 0

    for conversation in raw_data:
        conversations = conversation.get("conversations", [])
        for turn in conversations:
            # Only extract human/user messages
            role = turn.get("from", "")
            if role not in ("human", "user"):
                continue

            content = turn.get("value", "").strip()
            # Remove Unicode LS/PS characters that break editors
            content = content.replace("\u2028", "\n").replace("\u2029", "\n")
            if not content:
                continue

            total_extracted += 1

            # Quality filter
            if not passes_quality_filter(content, quality_filters):
                total_filtered += 1
                continue

            # Classify into token length bins
            token_count = count_tokens(content, model_name)
            for bin_name, bin_range in bins.items():
                if len(binned_turns[bin_name]) >= max_per_bin:
                    continue
                if is_in_token_range(
                    content,
                    bin_range["min_tokens"],
                    bin_range["max_tokens"],
                    model_name,
                ):
                    binned_turns[bin_name].append({
                        "turn_id": f"sharegpt_{bin_name}_{len(binned_turns[bin_name])}",
                        "token_length_bin": bin_name,
                        "token_count": token_count,
                        "content": content,
                    })
                    break

        # Early exit if all bins are full
        if all(len(v) >= max_per_bin for v in binned_turns.values()):
            break

    logger.info(
        "Extracted %d user turns, filtered %d, kept: %s",
        total_extracted,
        total_filtered,
        {k: len(v) for k, v in binned_turns.items()},
    )

    # Write output files
    processed_dir.mkdir(parents=True, exist_ok=True)
    for bin_name, turns in binned_turns.items():
        output_path = processed_dir / f"sharegpt_turns_{bin_name}.jsonl"
        with open(output_path, "w", encoding="utf-8") as f:
            for turn in turns:
                f.write(json.dumps(turn, ensure_ascii=False) + "\n")
        logger.info("Wrote %d turns to %s", len(turns), output_path)

    return binned_turns


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Preprocess ShareGPT dataset.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/preprocess.yaml",
        help="Path to preprocess config YAML.",
    )
    args = parser.parse_args()
    preprocess_sharegpt(args.config)

"""Preprocess MultiChallenge dataset for Phase 1 experiments.

Extracts user+assistant turn pairs from MultiChallenge conversations,
excludes TARGET_QUESTION (replaced by RuLES/IFEval probes),
preserves AXIS category labels.

Usage:
    python -m src.data_pipeline.preprocess_multichallenge --config configs/preprocess.yaml
"""

import argparse
import json
import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def extract_conversation_turns(conversation: list[dict]) -> list[dict]:
    """Extract structured turns from a MultiChallenge CONVERSATION field.

    Args:
        conversation: List of message dicts with 'role' and 'content'.

    Returns:
        List of turn dicts with role and content.
    """
    turns = []
    for msg in conversation:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            turns.append({"role": role, "content": content})
    return turns


def preprocess_multichallenge(config_path: str) -> list[dict]:
    """Run full MultiChallenge preprocessing pipeline.

    Args:
        config_path: Path to preprocess.yaml.

    Returns:
        List of processed conversation records.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    raw_dir = Path(cfg["paths"]["raw_dir"])
    processed_dir = Path(cfg["paths"]["processed_dir"])
    mc_cfg = cfg["multichallenge_preprocess"]

    input_file = (
        raw_dir
        / cfg["datasets"]["multichallenge"]["raw_subdir"]
        / "benchmark_questions.jsonl"
    )
    if not input_file.exists():
        logger.error("MultiChallenge data not found at %s", input_file)
        return []

    min_turns = mc_cfg.get("min_turns", 2)
    axis_categories = set(mc_cfg.get("axis_categories", []))
    exclude_target = mc_cfg.get("exclude_target_question", True)

    all_records: list[dict] = []

    logger.info("Loading MultiChallenge from %s ...", input_file)
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            record = json.loads(line)
            axis = record.get("AXIS", "")

            # Filter by AXIS category if specified
            if axis_categories and axis not in axis_categories:
                continue

            conversation = record.get("CONVERSATION", [])
            turns = extract_conversation_turns(conversation)

            # Filter by minimum turn count
            user_turns = [t for t in turns if t["role"] == "user"]
            if len(user_turns) < min_turns:
                continue

            # Exclude TARGET_QUESTION — we inject our own probes instead
            target_question = record.get("TARGET_QUESTION", "")

            processed = {
                "conversation_id": f"mc_{len(all_records)}",
                "source": "multichallenge",
                "axis": axis,
                "turns": turns,
                "turn_count": len(user_turns),
                "total_messages": len(turns),
                "excluded_target_question": target_question if exclude_target else "",
            }
            all_records.append(processed)

    logger.info(
        "Processed %d MultiChallenge conversations (axis distribution: %s)",
        len(all_records),
        _count_by_axis(all_records),
    )

    # Write output
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_path = processed_dir / "multichallenge_conversations.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    logger.info("Wrote %d records to %s", len(all_records), output_path)
    return all_records


def _count_by_axis(records: list[dict]) -> dict[str, int]:
    """Count records by AXIS category.

    Args:
        records: List of processed records.

    Returns:
        Dict mapping axis name to count.
    """
    counts: dict[str, int] = {}
    for rec in records:
        axis = rec.get("axis", "unknown")
        counts[axis] = counts.get(axis, 0) + 1
    return counts


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Preprocess MultiChallenge dataset.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/preprocess.yaml",
        help="Path to preprocess config YAML.",
    )
    args = parser.parse_args()
    preprocess_multichallenge(args.config)

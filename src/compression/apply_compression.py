"""Orchestrator: apply compression methods to experiment cases.

Reads Phase 1 experiment_cases.jsonl, applies each enabled compression
method with each parameter variant, and writes compressed case files.

Usage:
    python -m src.compression.apply_compression --config configs/compression.yaml
"""

import argparse
import copy
import json
import logging
from pathlib import Path

import yaml

from src.compression.base import BaseCompressor
from src.compression.selective_context import SelectiveContextCompressor
from src.compression.sliding_window import SlidingWindowCompressor
from src.compression.summarize_turns import SummarizeTurnsCompressor
from src.compression.system_prompt_reinforce import SystemPromptReinforceCompressor

logger = logging.getLogger(__name__)

# Registry of available compressors
COMPRESSOR_REGISTRY: dict[str, type[BaseCompressor]] = {
    "sliding_window": SlidingWindowCompressor,
    "selective_context": SelectiveContextCompressor,
    "summarize_turns": SummarizeTurnsCompressor,
    "system_prompt_reinforce": SystemPromptReinforceCompressor,
}


def register_compressor(name: str, cls: type[BaseCompressor]) -> None:
    """Register a compressor class in the global registry.

    Args:
        name: Method name key.
        cls: Compressor class.
    """
    COMPRESSOR_REGISTRY[name] = cls


def load_cases(path: Path) -> list[dict]:
    """Load experiment cases from JSONL.

    Args:
        path: Path to experiment_cases.jsonl.

    Returns:
        List of case dicts.
    """
    cases = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    logger.info("Loaded %d cases from %s", len(cases), path)
    return cases


def filter_cases(cases: list[dict], min_turn_count: int) -> list[dict]:
    """Filter cases to only those with sufficient turns for compression.

    Args:
        cases: All experiment cases.
        min_turn_count: Minimum turn_count to include.

    Returns:
        Filtered list of cases.
    """
    filtered = [c for c in cases if c["condition"]["turn_count"] >= min_turn_count]
    logger.info(
        "Filtered to %d cases (min_turn_count=%d)", len(filtered), min_turn_count
    )
    return filtered


def apply_single_method(
    compressor: BaseCompressor,
    cases: list[dict],
    params: dict,
    variant_name: str,
) -> list[dict]:
    """Apply a single compression method+params to all cases.

    Args:
        compressor: Compressor instance.
        cases: Filtered experiment cases.
        params: Method-specific parameters.
        variant_name: Human-readable variant name (e.g., "sliding_window_3").

    Returns:
        List of compressed case dicts.
    """
    compressed_cases = []
    for case in cases:
        new_case = copy.deepcopy(case)

        compressed_turns, metadata = compressor.compress(
            system_prompt=case["system_prompt"],
            intermediate_turns=case["intermediate_turns"],
            params=params,
        )

        new_case["original_case_id"] = case["case_id"]
        new_case["case_id"] = f"{case['case_id']}_{variant_name}"
        new_case["intermediate_turns"] = compressed_turns
        new_case["condition"]["compression_method"] = compressor.method_name
        new_case["condition"]["compression_params"] = params
        new_case["compression_metadata"] = metadata

        compressed_cases.append(new_case)

    logger.info(
        "Applied %s to %d cases", variant_name, len(compressed_cases)
    )
    return compressed_cases


def write_cases(cases: list[dict], output_path: Path) -> None:
    """Write compressed cases to JSONL.

    Args:
        cases: Compressed case dicts.
        output_path: Output file path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
    logger.info("Wrote %d cases to %s", len(cases), output_path)


def run_compression(config_path: str) -> dict[str, list[dict]]:
    """Run all enabled compression methods on experiment cases.

    Args:
        config_path: Path to compression.yaml.

    Returns:
        Dict mapping variant_name to list of compressed cases.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    input_path = Path(cfg["paths"]["input_cases"])
    output_dir = Path(cfg["paths"]["output_dir"])
    min_turns = cfg["filter"]["min_turn_count"]
    methods_cfg = cfg["compression_methods"]

    all_cases = load_cases(input_path)
    eligible_cases = filter_cases(all_cases, min_turns)

    all_results: dict[str, list[dict]] = {}

    for method_name, method_cfg in methods_cfg.items():
        if not method_cfg.get("enabled", False):
            logger.info("Skipping disabled method: %s", method_name)
            continue

        if method_name not in COMPRESSOR_REGISTRY:
            logger.warning("No compressor registered for: %s", method_name)
            continue

        compressor = COMPRESSOR_REGISTRY[method_name]()

        # Generate parameter variants
        variants = _build_variants(method_name, method_cfg)

        for variant_name, params in variants:
            compressed = apply_single_method(
                compressor, eligible_cases, params, variant_name
            )
            variant_dir = output_dir / variant_name
            write_cases(compressed, variant_dir / "experiment_cases.jsonl")
            all_results[variant_name] = compressed

    # Summary
    total = sum(len(v) for v in all_results.values())
    logger.info(
        "Compression complete: %d variants, %d total cases",
        len(all_results), total,
    )
    return all_results


def _build_variants(method_name: str, method_cfg: dict) -> list[tuple[str, dict]]:
    """Build (variant_name, params) pairs from method config.

    Args:
        method_name: Compression method name.
        method_cfg: Method-specific config dict.

    Returns:
        List of (variant_name, params_dict) tuples.
    """
    variants: list[tuple[str, dict]] = []

    if method_name == "sliding_window":
        for ws in method_cfg.get("window_sizes", []):
            variants.append((f"sliding_window_{ws}", {"window_size": ws}))

    elif method_name == "selective_context":
        for ratio in method_cfg.get("target_ratios", []):
            ratio_str = str(int(ratio * 100)).zfill(3)
            variants.append((
                f"selective_context_{ratio_str}",
                {"target_ratio": ratio},
            ))

    elif method_name == "summarize_turns":
        variants.append(("summarize_turns", {
            "model": method_cfg.get("model", ""),
            "max_summary_tokens": method_cfg.get("max_summary_tokens", 50),
            "temperature": method_cfg.get("temperature", 0.0),
            "batch_size": method_cfg.get("batch_size", 10),
        }))

    elif method_name == "system_prompt_reinforce":
        for interval in method_cfg.get("injection_intervals", []):
            variants.append((
                f"reinforce_{interval}",
                {
                    "injection_interval": interval,
                    "max_reminder_tokens": method_cfg.get("max_reminder_tokens", 100),
                },
            ))

    return variants


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Apply compression to experiment cases.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/compression.yaml",
        help="Path to compression config YAML.",
    )
    args = parser.parse_args()
    run_compression(args.config)

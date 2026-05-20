"""Phase 1 data pipeline entry point.

Orchestrates the full preprocessing pipeline:
1. Download raw datasets
2. Preprocess each dataset
3. Generate experiment cases (~104 cases)

Usage:
    python -m src.data_pipeline.load_datasets --config configs/preprocess.yaml
    python -m src.data_pipeline.load_datasets --config configs/preprocess.yaml --skip-download
"""

import argparse
import logging

from src.data_pipeline.download_datasets import main as download_all
from src.data_pipeline.generate_experiment_cases import generate_cases
from src.data_pipeline.preprocess_ifeval import preprocess_ifeval
from src.data_pipeline.preprocess_multichallenge import preprocess_multichallenge
from src.data_pipeline.preprocess_rules import preprocess_rules
from src.data_pipeline.preprocess_sharegpt import preprocess_sharegpt

logger = logging.getLogger(__name__)


def run_pipeline(config_path: str, skip_download: bool = False) -> None:
    """Run the full Phase 1 data pipeline.

    Args:
        config_path: Path to preprocess.yaml.
        skip_download: If True, skip the download step (assume raw data exists).
    """
    # Step 1: Download raw datasets
    if not skip_download:
        logger.info("=== Step 1: Downloading datasets ===")
        download_all(config_path)
    else:
        logger.info("=== Step 1: Skipping download (--skip-download) ===")

    # Step 2: Preprocess each dataset
    logger.info("=== Step 2: Preprocessing RuLES ===")
    rules_probes = preprocess_rules(config_path)
    logger.info("  -> %d RuLES probes", len(rules_probes))

    logger.info("=== Step 3: Preprocessing IFEval ===")
    ifeval_probes = preprocess_ifeval(config_path)
    logger.info("  -> %d IFEval probes", len(ifeval_probes))

    logger.info("=== Step 4: Preprocessing ShareGPT ===")
    sharegpt_turns = preprocess_sharegpt(config_path)
    for bin_name, turns in sharegpt_turns.items():
        logger.info("  -> %d ShareGPT turns (%s)", len(turns), bin_name)

    logger.info("=== Step 5: Preprocessing MultiChallenge ===")
    mc_convs = preprocess_multichallenge(config_path)
    logger.info("  -> %d MultiChallenge conversations", len(mc_convs))

    # Step 3: Generate experiment cases
    logger.info("=== Step 6: Generating experiment cases ===")
    cases = generate_cases(config_path)
    logger.info("  -> %d experiment cases generated", len(cases))

    logger.info("=== Pipeline complete ===")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Run Phase 1 data pipeline.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/preprocess.yaml",
        help="Path to preprocess config YAML.",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip dataset download step.",
    )
    args = parser.parse_args()
    run_pipeline(args.config, skip_download=args.skip_download)

"""Download and stage raw datasets for Phase 1 pipeline.

Datasets:
- RuLES: git sparse-checkout from GitHub (scenarios/ + data/)
- IFEval: HuggingFace datasets library
- ShareGPT: HuggingFace Hub file download
- MultiChallenge: local copy from GoogleCloud path

Usage:
    python -m src.data_pipeline.download_datasets --config configs/preprocess.yaml
"""

import argparse
import logging
import shutil
import subprocess
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load YAML configuration file.

    Args:
        config_path: Path to the YAML config file.

    Returns:
        Parsed configuration dictionary.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def download_rules(raw_dir: Path, cfg: dict) -> None:
    """Download RuLES dataset via git sparse-checkout.

    Args:
        raw_dir: Base raw data directory.
        cfg: Dataset config for RuLES.
    """
    target = raw_dir / cfg["raw_subdir"]
    if target.exists() and any(target.iterdir()):
        logger.info("RuLES already downloaded at %s, skipping.", target)
        return

    target.mkdir(parents=True, exist_ok=True)
    logger.info("Cloning RuLES (sparse-checkout) into %s ...", target)

    subprocess.run(
        ["git", "clone", "--filter=blob:none", "--no-checkout", cfg["github_url"], str(target)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(target), "sparse-checkout", "init", "--cone"],
        check=True,
    )
    sparse_paths = cfg.get("sparse_paths", ["scenarios", "data"])
    subprocess.run(
        ["git", "-C", str(target), "sparse-checkout", "set"] + sparse_paths,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(target), "checkout"],
        check=True,
    )
    logger.info("RuLES download complete.")


def download_ifeval(raw_dir: Path, cfg: dict) -> None:
    """Download IFEval dataset from HuggingFace.

    Args:
        raw_dir: Base raw data directory.
        cfg: Dataset config for IFEval.
    """
    target = raw_dir / cfg["raw_subdir"]
    output_file = target / "ifeval.jsonl"
    if output_file.exists():
        logger.info("IFEval already downloaded at %s, skipping.", output_file)
        return

    target.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading IFEval from HuggingFace (%s) ...", cfg["hf_repo_id"])

    from datasets import load_dataset

    ds = load_dataset(cfg["hf_repo_id"], split=cfg.get("hf_split", "train"))
    ds.to_json(str(output_file), force_ascii=False)
    logger.info("IFEval saved to %s (%d records).", output_file, len(ds))


def download_sharegpt(raw_dir: Path, cfg: dict) -> None:
    """Download ShareGPT dataset from HuggingFace Hub.

    Args:
        raw_dir: Base raw data directory.
        cfg: Dataset config for ShareGPT.
    """
    target = raw_dir / cfg["raw_subdir"]
    output_file = target / cfg["hf_filename"]
    if output_file.exists():
        logger.info("ShareGPT already downloaded at %s, skipping.", output_file)
        return

    target.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading ShareGPT from HuggingFace Hub (%s) ...", cfg["hf_repo_id"])

    from huggingface_hub import hf_hub_download

    hf_hub_download(
        repo_id=cfg["hf_repo_id"],
        filename=cfg["hf_filename"],
        repo_type="dataset",
        local_dir=str(target),
    )
    logger.info("ShareGPT saved to %s.", output_file)


def download_multichallenge(raw_dir: Path, cfg: dict, source_path: str) -> None:
    """Copy MultiChallenge dataset from local GoogleCloud path.

    Args:
        raw_dir: Base raw data directory.
        cfg: Dataset config for MultiChallenge.
        source_path: Local path to benchmark_questions.jsonl.
    """
    target = raw_dir / cfg["raw_subdir"]
    output_file = target / "benchmark_questions.jsonl"
    if output_file.exists():
        logger.info("MultiChallenge already present at %s, skipping.", output_file)
        return

    target.mkdir(parents=True, exist_ok=True)
    source = Path(source_path)
    if not source.exists():
        logger.warning(
            "MultiChallenge source not found: %s — skipping. "
            "Place benchmark_questions.jsonl manually at %s to use this dataset.",
            source, output_file,
        )
        return

    shutil.copy2(str(source), str(output_file))
    logger.info("MultiChallenge copied to %s.", output_file)


def main(config_path: str) -> None:
    """Run all dataset downloads.

    Args:
        config_path: Path to preprocess.yaml.
    """
    cfg = load_config(config_path)
    raw_dir = Path(cfg["paths"]["raw_dir"])
    datasets_cfg = cfg["datasets"]

    download_rules(raw_dir, datasets_cfg["rules"])
    download_ifeval(raw_dir, datasets_cfg["ifeval"])
    download_sharegpt(raw_dir, datasets_cfg["sharegpt"])
    download_multichallenge(
        raw_dir,
        datasets_cfg["multichallenge"],
        cfg["paths"]["multichallenge_source"],
    )

    logger.info("All datasets downloaded successfully.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Download raw datasets for Phase 1.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/preprocess.yaml",
        help="Path to preprocess config YAML.",
    )
    args = parser.parse_args()
    main(args.config)

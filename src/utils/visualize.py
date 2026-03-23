"""Visualization module for Phase 1/2 evaluation results.

Generates compliance rate curves, compression ratio comparisons,
and defense effectiveness charts.

Usage:
    python -m src.utils.visualize --report reports/evaluation_summary.json --output reports/figures/
"""

import argparse
import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)

# Color palette for compression methods
METHOD_COLORS: dict[str, str] = {
    "none": "#333333",
    "sliding_window": "#1f77b4",
    "selective_context": "#ff7f0e",
    "summarize_turns": "#2ca02c",
    "system_prompt_reinforce": "#d62728",
}

METHOD_LABELS: dict[str, str] = {
    "none": "No Compression (Baseline)",
    "sliding_window": "Sliding Window",
    "selective_context": "Selective Context",
    "summarize_turns": "Turn Summarization",
    "system_prompt_reinforce": "Prompt Reinforcement",
}


def plot_compliance_curves(report: dict, output_dir: Path) -> None:
    """Plot compliance rate vs turn count for each method.

    Args:
        report: Evaluation summary dict.
        output_dir: Directory for output figures.
    """
    summary = report.get("compliance_by_method_and_turns", {})
    if not summary:
        logger.warning("No compliance data to plot")
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    for method, turn_data in sorted(summary.items()):
        base_method = _get_base_method(method)
        color = METHOD_COLORS.get(base_method, "#888888")
        label = f"{METHOD_LABELS.get(base_method, method)}"
        if method != base_method:
            suffix = method.replace(base_method + "_", "")
            label += f" ({suffix})"

        turn_counts = sorted(int(tc) for tc in turn_data.keys())
        rates = [turn_data[str(tc)]["compliance_rate"] for tc in turn_counts]

        linestyle = "-" if base_method == "none" else "--"
        linewidth = 2.5 if base_method == "none" else 1.5
        ax.plot(
            turn_counts, rates,
            marker="o", color=color,
            linestyle=linestyle, linewidth=linewidth,
            label=label, markersize=5,
        )

    ax.set_xlabel("Turn Count", fontsize=12)
    ax.set_ylabel("Compliance Rate", fontsize=12)
    ax.set_title("System Prompt Compliance vs. Turn Count by Compression Method", fontsize=13)
    ax.set_ylim(-0.05, 1.05)
    ax.legend(loc="lower left", fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3)

    output_path = output_dir / "compliance_curves.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved compliance curves to %s", output_path)


def plot_compression_vs_compliance(report: dict, output_dir: Path) -> None:
    """Scatter plot: average compression ratio vs compliance rate per method.

    Args:
        report: Evaluation summary dict.
        output_dir: Directory for output figures.
    """
    summary = report.get("compliance_by_method_and_turns", {})
    ratios = report.get("avg_compression_ratios", {})

    if not summary or not ratios:
        logger.warning("Insufficient data for compression vs compliance plot")
        return

    fig, ax = plt.subplots(figsize=(8, 6))

    for method, turn_data in sorted(summary.items()):
        if method == "none":
            continue
        avg_ratio = ratios.get(method)
        if avg_ratio is None:
            continue

        base_method = _get_base_method(method)
        color = METHOD_COLORS.get(base_method, "#888888")

        all_rates = [v["compliance_rate"] for v in turn_data.values()]
        avg_compliance = np.mean(all_rates) if all_rates else 0.0

        suffix = method.replace(base_method + "_", "") if method != base_method else ""
        label = f"{METHOD_LABELS.get(base_method, method)}"
        if suffix:
            label += f" ({suffix})"

        ax.scatter(
            avg_ratio, avg_compliance,
            color=color, s=100, zorder=5,
            label=label, edgecolors="black", linewidths=0.5,
        )

    ax.set_xlabel("Compression Ratio (lower = more compression)", fontsize=12)
    ax.set_ylabel("Average Compliance Rate", fontsize=12)
    ax.set_title("Compression Ratio vs. Compliance", fontsize=13)
    ax.set_ylim(-0.05, 1.05)
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, alpha=0.3)

    output_path = output_dir / "compression_vs_compliance.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved compression vs compliance to %s", output_path)


def plot_defense_effectiveness(report: dict, output_dir: Path) -> None:
    """Bar chart of defense effectiveness per method.

    Args:
        report: Evaluation summary dict.
        output_dir: Directory for output figures.
    """
    metrics = report.get("phase2_metrics", {})
    if not metrics:
        logger.warning("No phase2 metrics for defense effectiveness plot")
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    methods = sorted(metrics.keys())
    x_labels = []
    x_vals = []
    colors = []

    for method in methods:
        turn_data = metrics[method]
        base_method = _get_base_method(method)
        color = METHOD_COLORS.get(base_method, "#888888")

        for tc in sorted(turn_data.keys(), key=int):
            eff = turn_data[tc].get("defense_effectiveness", 0.0)
            suffix = method.replace(base_method + "_", "") if method != base_method else ""
            label = f"{suffix or base_method}\nt={tc}"
            x_labels.append(label)
            x_vals.append(eff)
            colors.append(color)

    x_pos = np.arange(len(x_labels))
    ax.bar(x_pos, x_vals, color=colors, edgecolor="black", linewidth=0.3)

    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_labels, fontsize=7, rotation=45, ha="right")
    ax.set_ylabel("Defense Effectiveness", fontsize=12)
    ax.set_title("Defense Effectiveness by Method and Turn Count", fontsize=13)
    ax.axhline(y=0, color="black", linewidth=0.5)
    ax.grid(True, axis="y", alpha=0.3)

    output_path = output_dir / "defense_effectiveness.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved defense effectiveness to %s", output_path)


def generate_all_plots(report_path: str, output_dir: str) -> None:
    """Generate all visualization plots from an evaluation report.

    Args:
        report_path: Path to evaluation_summary.json.
        output_dir: Directory for output figures.
    """
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    plot_compliance_curves(report, out_path)
    plot_compression_vs_compliance(report, out_path)
    plot_defense_effectiveness(report, out_path)

    logger.info("All plots generated in %s", output_dir)


def _get_base_method(variant_name: str) -> str:
    """Extract base method name from variant name.

    Args:
        variant_name: e.g., 'sliding_window_3' or 'selective_context_050'.

    Returns:
        Base method name, e.g., 'sliding_window'.
    """
    for base in METHOD_COLORS:
        if variant_name.startswith(base):
            return base
    return variant_name


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Generate evaluation visualizations.")
    parser.add_argument(
        "--report", type=str, default="reports/evaluation_summary.json",
        help="Path to evaluation summary JSON.",
    )
    parser.add_argument(
        "--output", type=str, default="reports/figures",
        help="Output directory for figures.",
    )
    args = parser.parse_args()
    generate_all_plots(args.report, args.output)

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

# Set Korean font for macOS
plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False

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
    "none": "압축 없음 (베이스라인)",
    "sliding_window": "슬라이딩 윈도우",
    "selective_context": "선택적 컨텍스트",
    "summarize_turns": "대화 턴 요약",
    "system_prompt_reinforce": "시스템 프롬프트 강화",
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

    ax.set_xlabel("턴 수", fontsize=12)
    ax.set_ylabel("준수율", fontsize=12)
    ax.set_title("압축 기법별 턴 수에 따른 시스템 프롬프트 준수율", fontsize=13)
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

    ax.set_xlabel("압축 비율 (낮을수록 압축률 높음)", fontsize=12)
    ax.set_ylabel("평균 준수율", fontsize=12)
    ax.set_title("압축 비율 대비 준수율", fontsize=13)
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
            base_label = METHOD_LABELS.get(base_method, base_method)
            label_name = f"{base_label} ({suffix})" if suffix else base_label
            label = f"{label_name}\nt={tc}"
            x_labels.append(label)
            x_vals.append(eff)
            colors.append(color)

    x_pos = np.arange(len(x_labels))
    ax.bar(x_pos, x_vals, color=colors, edgecolor="black", linewidth=0.3)

    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_labels, fontsize=7, rotation=45, ha="right")
    ax.set_ylabel("방어 효과성", fontsize=12)
    ax.set_title("기법 및 턴 수에 따른 방어 효과성", fontsize=13)
    ax.axhline(y=0, color="black", linewidth=0.5)
    ax.grid(True, axis="y", alpha=0.3)

    output_path = output_dir / "defense_effectiveness.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved defense effectiveness to %s", output_path)


def plot_rule_count_compliance(report: dict, output_dir: Path) -> None:
    """Plot compliance rate vs rule count (aggregated across turns).

    Args:
        report: Evaluation summary dict.
        output_dir: Directory for output figures.
    """
    rc_data = report.get("compliance_by_rule_count_and_turns", {})
    if not rc_data:
        logger.warning("No rule_count data for compliance plot")
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    # Aggregate compliance per rule count (across all turns)
    rule_counts = sorted(int(rc) for rc in rc_data.keys())
    overall_rates = []
    for rc in rule_counts:
        all_scores = []
        for tc_data in rc_data[str(rc)].values():
            rate = tc_data["compliance_rate"]
            n = tc_data["n"]
            all_scores.extend([rate] * n)
        overall_rate = sum(all_scores) / len(all_scores) if all_scores else 0
        overall_rates.append(overall_rate)

    ax.plot(
        rule_counts, overall_rates,
        marker="s", color="#e74c3c", linewidth=2.5, markersize=10,
        label="전체 평균 준수율", zorder=5,
    )

    # Also plot per turn count
    turn_counts = set()
    for tc_groups in rc_data.values():
        turn_counts.update(int(tc) for tc in tc_groups.keys())
    turn_counts = sorted(turn_counts)

    tc_colors = {0: "#2c3e50", 2: "#3498db", 4: "#f39c12", 6: "#e67e22"}
    for tc in turn_counts:
        rates = []
        for rc in rule_counts:
            tc_data = rc_data[str(rc)].get(str(tc), {})
            rates.append(tc_data.get("compliance_rate", 0))
        ax.plot(
            rule_counts, rates,
            marker="o", color=tc_colors.get(tc, "#888"),
            linestyle="--", linewidth=1.2, markersize=6, alpha=0.7,
            label=f"턴 {tc}",
        )

    ax.set_xlabel("시스템 프롬프트 규칙 수", fontsize=12)
    ax.set_ylabel("준수율", fontsize=12)
    ax.set_title("규칙 수에 따른 시스템 프롬프트 준수율 변화", fontsize=13)
    ax.set_ylim(-0.05, 1.05)
    ax.set_xticks(rule_counts)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3)

    output_path = output_dir / "rule_count_compliance.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved rule count compliance to %s", output_path)


def plot_rule_token_heatmap(report: dict, output_dir: Path) -> None:
    """Heatmap: compliance rate by rule_count × token_length.

    Args:
        report: Evaluation summary dict.
        output_dir: Directory for output figures.
    """
    rtl_data = report.get("compliance_by_rule_count_and_token_length", {})
    if not rtl_data:
        logger.warning("No rule_count × token_length data for heatmap")
        return

    rule_counts = sorted(int(rc) for rc in rtl_data.keys())
    token_lengths = ["none", "short", "medium", "long", "fixed"]
    # Filter to only existing token lengths
    existing_tl = set()
    for rc_data in rtl_data.values():
        existing_tl.update(rc_data.keys())
    token_lengths = [tl for tl in token_lengths if tl in existing_tl]

    tl_labels = {
        "none": "없음 (베이스라인)",
        "short": "짧은 (~100tok)",
        "medium": "중간 (~300tok)",
        "long": "긴 (~500tok)",
        "fixed": "고정 (MC)",
    }

    matrix = np.zeros((len(rule_counts), len(token_lengths)))
    for i, rc in enumerate(rule_counts):
        for j, tl in enumerate(token_lengths):
            data = rtl_data.get(str(rc), {}).get(tl, {})
            matrix[i, j] = data.get("compliance_rate", 0)

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(matrix, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")

    ax.set_xticks(range(len(token_lengths)))
    ax.set_xticklabels([tl_labels.get(tl, tl) for tl in token_lengths], fontsize=9)
    ax.set_yticks(range(len(rule_counts)))
    ax.set_yticklabels([f"규칙 {rc}개" for rc in rule_counts], fontsize=10)

    # Annotate cells
    for i in range(len(rule_counts)):
        for j in range(len(token_lengths)):
            val = matrix[i, j]
            color = "white" if val < 0.3 or val > 0.7 else "black"
            ax.text(j, i, f"{val:.0%}", ha="center", va="center", color=color,
                    fontsize=11, fontweight="bold")

    ax.set_title("규칙 수 × 토큰 길이별 준수율 히트맵", fontsize=13)
    fig.colorbar(im, ax=ax, label="준수율", shrink=0.8)

    output_path = output_dir / "rule_token_heatmap.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved rule × token heatmap to %s", output_path)


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
    plot_rule_count_compliance(report, out_path)
    plot_rule_token_heatmap(report, out_path)
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

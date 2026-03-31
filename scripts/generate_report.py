"""Generate experiment report + visualizations from partial or complete results.

Re-runnable: reads whatever data is available and produces updated report + charts.

Usage:
    python3 scripts/generate_report.py                    # default results
    python3 scripts/generate_report.py --input data/outputs/main_experiment/results_*.jsonl
"""

import argparse
import glob
import json
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Korean font setup
for font_name in ["AppleGothic", "NanumGothic", "Malgun Gothic"]:
    if any(font_name in f.name for f in fm.fontManager.ttflist):
        plt.rcParams["font.family"] = font_name
        break
plt.rcParams["axes.unicode_minus"] = False

REPORT_DIR = ROOT / "docs" / "outputs"
FIG_DIR = REPORT_DIR / "figures"


def load_results(input_patterns: list[str]) -> list[dict]:
    """Load all results from JSONL files matching patterns."""
    records: list[dict] = []
    for pattern in input_patterns:
        for path in sorted(glob.glob(pattern)):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
    return records


# ============================================================
# Chart 1: Compliance trajectory by rule_count (Q1)
# ============================================================

def chart_compliance_by_rule_count(records: list[dict]) -> None:
    """Compliance over turns, grouped by rule_count. One line per level."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharey=True)

    for ax, attack in zip(axes, ["benign", "adversarial"]):
        subset = [r for r in records if r["attack_intensity"] == attack]
        by_rc: dict[int, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))

        for r in subset:
            for t in r["turn_results"]:
                by_rc[r["rule_count"]][t["turn"]].append(t["compliance_rate"] * 100)

        for rc in sorted(by_rc.keys()):
            turns = sorted(by_rc[rc].keys())
            means = [np.mean(by_rc[rc][t]) for t in turns]
            stds = [np.std(by_rc[rc][t]) for t in turns]
            ax.errorbar(turns, means, yerr=stds, marker="o", linewidth=2,
                        markersize=5, capsize=3, label=f"R={rc}")

        ax.set_xlabel("Turn", fontsize=12)
        ax.set_ylabel("Compliance Rate (%)", fontsize=12)
        ax.set_title(f"Q1: Compliance by Rule Count ({attack})", fontsize=13)
        ax.set_ylim(-5, 105)
        ax.axhline(y=80, color="orange", linestyle="--", alpha=0.4, linewidth=1)
        ax.axhline(y=50, color="red", linestyle="--", alpha=0.4, linewidth=1)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(FIG_DIR / "q1_compliance_by_rule_count.png", dpi=150)
    plt.close()
    logger.info("Saved q1_compliance_by_rule_count.png")


# ============================================================
# Chart 2: Per-rule-type compliance (Q2)
# ============================================================

def chart_per_rule_type(records: list[dict]) -> None:
    """Average compliance per rule type over turns."""
    type_turns: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))

    for r in records:
        for t in r["turn_results"]:
            for s in t["scores"]:
                if s["pass"] is not None:
                    rtype = _get_rule_type(s["rule_id"], r.get("rules", []))
                    type_turns[rtype][t["turn"]].append(1.0 if s["pass"] else 0.0)

    if not type_turns:
        logger.warning("No per-rule-type data available")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    markers = {"language": "o", "format": "s", "behavioral": "D", "persona": "^"}
    colors = {"language": "#2196F3", "format": "#4CAF50", "behavioral": "#F44336", "persona": "#9C27B0"}

    for rtype in sorted(type_turns.keys()):
        turns = sorted(type_turns[rtype].keys())
        means = [np.mean(type_turns[rtype][t]) * 100 for t in turns]
        ax.plot(turns, means, marker=markers.get(rtype, "o"), linewidth=2,
                color=colors.get(rtype, "gray"), markersize=6, label=rtype)

    ax.set_xlabel("Turn", fontsize=12)
    ax.set_ylabel("Per-Rule Pass Rate (%)", fontsize=12)
    ax.set_title("Q2: Compliance by Rule Type", fontsize=14)
    ax.set_ylim(-5, 105)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "q2_per_rule_type.png", dpi=150)
    plt.close()
    logger.info("Saved q2_per_rule_type.png")


def _get_rule_type(rule_id: str, rules: list[dict]) -> str:
    for r in rules:
        if r.get("rule_id") == rule_id:
            return r.get("type", "unknown")
    return "unknown"


# ============================================================
# Chart 3: Benign vs Adversarial (Q3)
# ============================================================

def chart_benign_vs_adversarial(records: list[dict]) -> None:
    """Compliance comparison between benign and adversarial conditions."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    rule_counts = sorted(set(r["rule_count"] for r in records))

    for idx, rc in enumerate(rule_counts[:4]):
        ax = axes[idx // 2][idx % 2]

        for attack, style, color in [("benign", "-", "#2196F3"), ("adversarial", "--", "#F44336")]:
            subset = [r for r in records if r["rule_count"] == rc and r["attack_intensity"] == attack]
            turn_data: dict[int, list[float]] = defaultdict(list)
            for r in subset:
                for t in r["turn_results"]:
                    turn_data[t["turn"]].append(t["compliance_rate"] * 100)

            if turn_data:
                turns = sorted(turn_data.keys())
                means = [np.mean(turn_data[t]) for t in turns]
                stds = [np.std(turn_data[t]) for t in turns]
                ax.errorbar(turns, means, yerr=stds, marker="o", linewidth=2,
                            linestyle=style, color=color, capsize=3, label=attack)

        ax.set_title(f"R={rc}", fontsize=12)
        ax.set_ylim(-5, 105)
        ax.axhline(y=80, color="orange", linestyle=":", alpha=0.4)
        ax.axhline(y=50, color="red", linestyle=":", alpha=0.4)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_xlabel("Turn")
        ax.set_ylabel("Compliance (%)")

    fig.suptitle("Q3: Benign vs Adversarial Compliance Decay", fontsize=14, y=1.01)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "q3_benign_vs_adversarial.png", dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Saved q3_benign_vs_adversarial.png")


# ============================================================
# Chart 4: Heatmap — rule × turn compliance (representative case)
# ============================================================

def chart_heatmap(records: list[dict]) -> None:
    """Per-rule compliance heatmap for the highest rule_count adversarial case."""
    # Find a good candidate: high rule_count, adversarial, many turns
    candidates = [r for r in records
                  if r["rule_count"] >= 5 and r["attack_intensity"] == "adversarial"
                  and r["turn_count"] >= 10]
    if not candidates:
        candidates = [r for r in records if r["turn_count"] >= 5]
    if not candidates:
        return

    best = max(candidates, key=lambda r: r["rule_count"] * r["turn_count"])
    rule_ids = [s["rule_id"] for s in best["turn_results"][0]["scores"]]
    turn_nums = [t["turn"] for t in best["turn_results"]]

    matrix = []
    for t in best["turn_results"]:
        row = []
        for s in t["scores"]:
            if s["pass"] is True:
                row.append(1.0)
            elif s["pass"] is False:
                row.append(0.0)
            else:
                row.append(0.5)
        matrix.append(row)

    from matplotlib.colors import ListedColormap, BoundaryNorm
    from matplotlib.patches import Patch

    fig, ax = plt.subplots(figsize=(max(8, len(rule_ids)), max(6, len(turn_nums) * 0.5)))
    cmap = ListedColormap(["#e74c3c", "#f0e68c", "#2ecc71"])
    norm = BoundaryNorm([0, 0.25, 0.75, 1.0], cmap.N)

    im = ax.imshow(np.array(matrix), cmap=cmap, norm=norm, aspect="auto")
    ax.set_xticks(range(len(rule_ids)))
    ax.set_xticklabels(rule_ids, fontsize=9, rotation=45)
    ax.set_yticks(range(len(turn_nums)))
    ax.set_yticklabels([f"T{t}" for t in turn_nums], fontsize=9)
    ax.set_xlabel("Rule", fontsize=11)
    ax.set_ylabel("Turn", fontsize=11)
    ax.set_title(
        f"{best['case_id']}: R{best['rule_count']} T{best['turn_count']} "
        f"{best['attack_intensity']} (rep={best.get('rep', 0)})",
        fontsize=12,
    )

    legend_elements = [
        Patch(facecolor="#2ecc71", label="Pass"),
        Patch(facecolor="#f0e68c", label="N/A"),
        Patch(facecolor="#e74c3c", label="Fail"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=9)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "heatmap_representative.png", dpi=150)
    plt.close()
    logger.info("Saved heatmap_representative.png")


# ============================================================
# Summary table
# ============================================================

def compute_summary(records: list[dict]) -> dict:
    """Compute summary statistics."""
    summary: dict = {
        "total_runs": len(records),
        "models": list(set(r["model"] for r in records)),
        "timestamp": time.strftime("%Y-%m-%d %H:%M"),
    }

    # By condition: mean final compliance
    condition_stats: dict[str, list[float]] = defaultdict(list)
    for r in records:
        key = f"R{r['rule_count']}_T{r['turn_count']}_{r['attack_intensity']}"
        if r["turn_results"]:
            final = r["turn_results"][-1]["compliance_rate"]
            condition_stats[key].append(final)

    summary["condition_means"] = {
        k: {"mean": np.mean(v), "std": np.std(v), "n": len(v)}
        for k, v in sorted(condition_stats.items())
    }

    # Degradation onset (DO) and Collapse threshold (CT) detection
    do_ct: dict[str, dict] = {}
    for r in records:
        key = f"R{r['rule_count']}_{r['attack_intensity']}"
        if key not in do_ct:
            do_ct[key] = {"do_turns": [], "ct_turns": []}
        for t in r["turn_results"]:
            if t["compliance_rate"] < 0.8:
                do_ct[key]["do_turns"].append(t["turn"])
                break
        for t in r["turn_results"]:
            if t["compliance_rate"] < 0.5:
                do_ct[key]["ct_turns"].append(t["turn"])
                break

    summary["threshold_detection"] = {
        k: {
            "DO_mean_turn": np.mean(v["do_turns"]) if v["do_turns"] else None,
            "DO_n": len(v["do_turns"]),
            "CT_mean_turn": np.mean(v["ct_turns"]) if v["ct_turns"] else None,
            "CT_n": len(v["ct_turns"]),
        }
        for k, v in sorted(do_ct.items())
    }

    return summary


# ============================================================
# Markdown report
# ============================================================

def generate_markdown(records: list[dict], summary: dict) -> str:
    """Generate markdown report."""
    lines = [
        "# Compliance Decay Experiment — Interim Report",
        "",
        f"> **Generated**: {summary['timestamp']}",
        f"> **Runs analyzed**: {summary['total_runs']} / 1,540 (target)",
        f"> **Models**: {', '.join(summary['models'])}",
        "",
        "---",
        "",
        "## 1. Experiment Overview",
        "",
        "| Variable | Levels |",
        "|----------|--------|",
        "| rule_count | 1, 3, 5, 7 |",
        "| turn_count | 1, 5, 10, 15 |",
        "| attack_intensity | benign, adversarial |",
        "| repetitions | 5 per cell |",
        "| models | Llama 3.1 8B (vLLM) |",
        "",
        "---",
        "",
        "## 2. Key Findings",
        "",
    ]

    # Final compliance summary table
    lines.append("### 2.1 Final Compliance by Condition")
    lines.append("")
    lines.append("| Condition | Mean Compliance | Std | N |")
    lines.append("|-----------|----------------|-----|---|")
    for key, stats in summary["condition_means"].items():
        lines.append(
            f"| {key} | {stats['mean']*100:.1f}% | ±{stats['std']*100:.1f}% | {stats['n']} |"
        )
    lines.append("")

    # Threshold detection
    lines.append("### 2.2 Degradation Onset (DO < 80%) & Collapse Threshold (CT < 50%)")
    lines.append("")
    lines.append("| Condition | DO (mean turn) | DO cases | CT (mean turn) | CT cases |")
    lines.append("|-----------|---------------|----------|---------------|----------|")
    for key, td in summary["threshold_detection"].items():
        do_str = f"T{td['DO_mean_turn']:.1f}" if td["DO_mean_turn"] else "—"
        ct_str = f"T{td['CT_mean_turn']:.1f}" if td["CT_mean_turn"] else "—"
        lines.append(f"| {key} | {do_str} | {td['DO_n']} | {ct_str} | {td['CT_n']} |")
    lines.append("")

    # Charts
    lines.extend([
        "---",
        "",
        "## 3. Visualizations",
        "",
        "### 3.1 Q1: Compliance by Rule Count",
        "![Q1](figures/q1_compliance_by_rule_count.png)",
        "",
        "### 3.2 Q2: Per-Rule-Type Compliance",
        "![Q2](figures/q2_per_rule_type.png)",
        "",
        "### 3.3 Q3: Benign vs Adversarial",
        "![Q3](figures/q3_benign_vs_adversarial.png)",
        "",
        "### 3.4 Representative Heatmap",
        "![Heatmap](figures/heatmap_representative.png)",
        "",
        "---",
        "",
        "## 4. Preliminary Observations",
        "",
    ])

    # Auto-generate observations
    # Check adversarial vs benign gap
    benign_finals = [r["turn_results"][-1]["compliance_rate"]
                     for r in records if r["attack_intensity"] == "benign" and r["turn_results"]]
    adv_finals = [r["turn_results"][-1]["compliance_rate"]
                  for r in records if r["attack_intensity"] == "adversarial" and r["turn_results"]]

    if benign_finals and adv_finals:
        gap = (np.mean(benign_finals) - np.mean(adv_finals)) * 100
        lines.append(f"- **Adversarial impact**: {gap:.1f}pp lower compliance vs benign "
                     f"(benign: {np.mean(benign_finals)*100:.1f}%, "
                     f"adversarial: {np.mean(adv_finals)*100:.1f}%)")
    lines.append("")

    # Rule count effect
    for rc in sorted(set(r["rule_count"] for r in records)):
        rc_records = [r for r in records if r["rule_count"] == rc and r["turn_results"]]
        if rc_records:
            mean_final = np.mean([r["turn_results"][-1]["compliance_rate"] for r in rc_records])
            lines.append(f"- **R={rc}**: mean final compliance {mean_final*100:.1f}%")
    lines.append("")

    lines.extend([
        "---",
        "",
        "## 5. Status & Next Steps",
        "",
        f"- Data collection: {summary['total_runs']}/1,540 runs ({summary['total_runs']/1540*100:.1f}%)",
        "- [ ] Complete remaining repetitions",
        "- [ ] Add DeepSeek R1 model comparison",
        "- [ ] Statistical tests (ANOVA, dose-response fitting)",
        "- [ ] Final report generation",
    ])

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate experiment report.")
    parser.add_argument(
        "--input", nargs="+",
        default=[str(ROOT / "data" / "outputs" / "main_experiment" / "results_*.jsonl")],
        help="Glob patterns for result JSONL files.",
    )
    args = parser.parse_args()

    records = load_results(args.input)
    if not records:
        logger.error("No results found. Run the experiment first.")
        return

    logger.info("Loaded %d result records", len(records))

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate charts
    chart_compliance_by_rule_count(records)
    chart_per_rule_type(records)
    chart_benign_vs_adversarial(records)
    chart_heatmap(records)

    # Generate summary
    summary = compute_summary(records)

    # Write JSON summary
    with open(REPORT_DIR / "experiment_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    logger.info("Saved experiment_summary.json")

    # Write markdown report
    report = generate_markdown(records, summary)
    report_path = REPORT_DIR / "experiment_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("Saved %s", report_path)

    # Print quick summary
    print(f"\n{'='*60}")
    print(f"Report: {summary['total_runs']} runs analyzed")
    print(f"{'='*60}")
    for key, stats in list(summary["condition_means"].items())[:10]:
        print(f"  {key}: {stats['mean']*100:.1f}% ± {stats['std']*100:.1f}% (n={stats['n']})")
    if len(summary["condition_means"]) > 10:
        print(f"  ... and {len(summary['condition_means']) - 10} more conditions")


if __name__ == "__main__":
    main()

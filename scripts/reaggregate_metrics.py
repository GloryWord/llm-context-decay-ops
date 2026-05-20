"""Offline metric reaggregation for existing raw experiment results.

This script keeps the legacy partial-credit metric (`per_rule_pass_rate`) and
adds the stricter primary metric (`perfect_success`) plus adversarial
`targeted_rule_success` and `non_target_failure` when attack-target metadata is
available from the case file.

Usage:
    python3 scripts/reaggregate_metrics.py
    python3 scripts/reaggregate_metrics.py \
        --input data/outputs/main_experiment/fast_results_*.jsonl \
        --cases data/processed/experiment_cases_full.jsonl
"""

from __future__ import annotations

import argparse
import copy
import csv
import glob
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MPL_CACHE_DIR = ROOT / ".tmp" / "matplotlib"
MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, str(ROOT))

from src.evaluation.compliance_scorer import compute_turn_metrics


DEFAULT_INPUT_PATTERN = (
    ROOT
    / "data"
    / "outputs"
    / "main_experiment"
    / "fast_results_*.jsonl"
)
DEFAULT_CASES_FILE = ROOT / "data" / "processed" / "experiment_cases_full.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "outputs" / "reaggregated"
TURN_COUNTS = [1, 5, 10, 15]
RULE_COUNTS = [1, 3, 5, 7]
ATTACK_TYPES = ["benign", "adversarial"]
RULE_TYPE_ORDER = ["language", "format", "behavior", "persona"]
RULE_TYPE_LABELS = {
    "language": "Language",
    "format": "Format",
    "behavior": "Behavior",
    "behavioral": "Behavior",
    "persona": "Persona",
}
RULE_TYPE_COLORS = {
    "language": "#1f77b4",
    "format": "#d62728",
    "behavior": "#2ca02c",
    "behavioral": "#2ca02c",
    "persona": "#9467bd",
}

for font_name in ["AppleGothic", "NanumGothic", "Malgun Gothic"]:
    if any(font_name in f.name for f in fm.fontManager.ttflist):
        plt.rcParams["font.family"] = font_name
        break
plt.rcParams["axes.unicode_minus"] = False


def normalize_rule_type(rule_type: Any) -> str:
    """Normalize historical rule category aliases before aggregation/plotting."""
    normalized = str(rule_type or "unknown")
    if normalized == "behavioral":
        return "behavior"
    return normalized


def expand_inputs(patterns: list[str]) -> list[Path]:
    """Expand explicit paths/globs into a stable path list."""
    paths: list[Path] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if not matches and Path(pattern).exists():
            matches = [pattern]
        paths.extend(Path(match) for match in matches)
    return paths


def record_priority(record: dict[str, Any]) -> tuple[int, int]:
    """Prefer records with rule metadata and more turn results."""
    return (
        1 if record.get("rules") else 0,
        len(record.get("turn_results", [])),
    )


def record_temperature(record: dict[str, Any]) -> float:
    """Read generation temperature from a record, defaulting legacy rows to 0.0."""
    generation_config = record.get("generation_config", {})
    return float(record.get("temperature", generation_config.get("temperature", 0.0)))


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate repeated result rows without collapsing temperature sweeps."""
    chosen: dict[tuple[str, int, str, float], dict[str, Any]] = {}
    for record in records:
        key = (
            str(record.get("case_id", "")),
            int(record.get("rep", 0)),
            str(record.get("model", "")),
            record_temperature(record),
        )
        current = chosen.get(key)
        if current is None or record_priority(record) > record_priority(current):
            chosen[key] = record

    return sorted(
        chosen.values(),
        key=lambda r: (
            str(r.get("model", "")),
            record_temperature(r),
            int(r.get("rule_count", 0)),
            int(r.get("turn_count", 0)),
            str(r.get("attack_intensity", "")),
            str(r.get("case_id", "")),
            int(r.get("rep", 0)),
        ),
    )


def load_results(paths: list[Path]) -> list[dict[str, Any]]:
    """Load and deduplicate JSONL result records."""
    records: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
    return dedupe_records(records)


def load_case_metadata(cases_path: Path) -> dict[str, dict[str, Any]]:
    """Load case-level and per-turn attack metadata from the case JSONL file."""
    case_map: dict[str, dict[str, Any]] = {}
    with cases_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            case = json.loads(line)
            turns = {
                int(turn["turn"]): {
                    "attack_targets": turn.get("attack_targets", []),
                    "attack_mode": turn.get("attack_mode", ""),
                }
                for turn in case.get("conversation_template", [])
            }
            case_map[case["case_id"]] = {
                "attack_targets": case.get("attack_targets", []),
                "attack_mode": case.get("attack_mode", ""),
                "turns": turns,
            }
    return case_map


def enrich_record(
    record: dict[str, Any],
    case_metadata: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Attach metadata and metric bundle to every turn in a result record."""
    enriched = copy.deepcopy(record)
    case_meta = case_metadata.get(str(enriched.get("case_id", "")), {})

    enriched.setdefault("metric_schema_version", "2026-05-11-perfect-target-nontarget-v2")
    if case_meta:
        enriched["attack_targets"] = case_meta.get("attack_targets", [])
        enriched["attack_mode"] = case_meta.get("attack_mode", "")

    turn_meta = case_meta.get("turns", {})
    for turn_result in enriched.get("turn_results", []):
        turn_number = int(turn_result.get("turn", 0))
        metadata = turn_meta.get(turn_number, {})
        attack_targets = turn_result.get("attack_targets", metadata.get("attack_targets", []))
        attack_mode = turn_result.get("attack_mode", metadata.get("attack_mode", ""))

        turn_result["attack_targets"] = attack_targets
        turn_result["attack_mode"] = attack_mode

        metrics = compute_turn_metrics(turn_result.get("scores", []), attack_targets)
        turn_result["metrics"] = metrics
        turn_result["compliance_rate"] = metrics["per_rule_pass_rate"]

    return enriched


def enrich_records(
    records: list[dict[str, Any]],
    case_metadata: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Enrich every record with metric and attack-target metadata."""
    return [enrich_record(record, case_metadata) for record in records]


def stat(values: list[float]) -> dict[str, float | int]:
    """Return mean/std/n for a numeric list."""
    if not values:
        return {"mean": float("nan"), "std": float("nan"), "n": 0}
    return {
        "mean": mean(values),
        "std": pstdev(values) if len(values) > 1 else 0.0,
        "n": len(values),
    }


def quantile(values: list[int | float], q: float) -> float:
    """Return a simple linear-interpolated quantile for a numeric list."""
    if not values:
        return float("nan")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize_first_failures(first_failures: list[int], trajectories: int) -> dict[str, Any]:
    """Summarize first-failure turns for scorable rule trajectories."""
    failed = len(first_failures)
    if not first_failures:
        return {
            "trajectories": trajectories,
            "failed_trajectories": failed,
            "failure_rate": failed / trajectories if trajectories else "",
            "mean_first_failure_turn": "",
            "median_first_failure_turn": "",
            "p25_first_failure_turn": "",
            "p75_first_failure_turn": "",
            "min_first_failure_turn": "",
            "max_first_failure_turn": "",
        }

    return {
        "trajectories": trajectories,
        "failed_trajectories": failed,
        "failure_rate": failed / trajectories if trajectories else "",
        "mean_first_failure_turn": mean(first_failures),
        "median_first_failure_turn": median(first_failures),
        "p25_first_failure_turn": quantile(first_failures, 0.25),
        "p75_first_failure_turn": quantile(first_failures, 0.75),
        "min_first_failure_turn": min(first_failures),
        "max_first_failure_turn": max(first_failures),
    }


def build_condition_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build final-turn old-vs-perfect comparison rows by exact condition."""
    grouped: dict[tuple[float, int, int, str], dict[str, list[float]]] = defaultdict(
        lambda: {
            "per_rule_pass_rate": [],
            "perfect_success": [],
            "targeted_rule_success": [],
            "non_target_failure": [],
        }
    )

    for record in records:
        turn_results = record.get("turn_results", [])
        if not turn_results:
            continue
        final_turn = turn_results[-1]
        metrics = final_turn.get("metrics", {})
        key = (
            record_temperature(record),
            int(record.get("rule_count", 0)),
            int(record.get("turn_count", 0)),
            str(record.get("attack_intensity", "")),
        )
        grouped[key]["per_rule_pass_rate"].append(float(metrics["per_rule_pass_rate"]))
        grouped[key]["perfect_success"].append(float(metrics["perfect_success"]))
        targeted = metrics.get("targeted_rule_success")
        if targeted is not None:
            grouped[key]["targeted_rule_success"].append(float(targeted))
        non_target = metrics.get("non_target_failure")
        if non_target is not None:
            grouped[key]["non_target_failure"].append(float(non_target))

    rows: list[dict[str, Any]] = []
    for key, values in sorted(grouped.items()):
        temperature, rule_count, turn_count, attack = key
        old_stats = stat(values["per_rule_pass_rate"])
        perfect_stats = stat(values["perfect_success"])
        targeted_stats = stat(values["targeted_rule_success"])
        non_target_stats = stat(values["non_target_failure"])
        rows.append({
            "temperature": temperature,
            "rule_count": rule_count,
            "turn_count": turn_count,
            "attack_intensity": attack,
            "n": old_stats["n"],
            "per_rule_pass_rate_mean": old_stats["mean"],
            "per_rule_pass_rate_std": old_stats["std"],
            "perfect_success_mean": perfect_stats["mean"],
            "perfect_success_std": perfect_stats["std"],
            "gap_pp": (old_stats["mean"] - perfect_stats["mean"]) * 100,
            "targeted_rule_success_mean": targeted_stats["mean"],
            "targeted_rule_success_std": targeted_stats["std"],
            "targeted_n": targeted_stats["n"],
            "non_target_failure_mean": non_target_stats["mean"],
            "non_target_failure_std": non_target_stats["std"],
            "non_target_n": non_target_stats["n"],
        })
    return rows


def write_enriched_jsonl(records: list[dict[str, Any]], output_dir: Path) -> Path:
    """Write enriched result records to a JSONL artifact."""
    output_path = output_dir / "metrics_enriched_results.jsonl"
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return output_path


def write_condition_csv(rows: list[dict[str, Any]], output_dir: Path) -> Path:
    """Write condition comparison table as CSV."""
    output_path = output_dir / "old_vs_perfect_success_by_condition.csv"
    fieldnames = [
        "temperature",
        "rule_count",
        "turn_count",
        "attack_intensity",
        "n",
        "per_rule_pass_rate_mean",
        "per_rule_pass_rate_std",
        "perfect_success_mean",
        "perfect_success_std",
        "gap_pp",
        "targeted_rule_success_mean",
        "targeted_rule_success_std",
        "targeted_n",
        "non_target_failure_mean",
        "non_target_failure_std",
        "non_target_n",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def _fmt_pct(value: float | int | None) -> str:
    """Format a ratio as a percentage for markdown."""
    if value is None or (isinstance(value, float) and value != value):
        return "N/A"
    return f"{float(value) * 100:.1f}%"


def write_condition_markdown(rows: list[dict[str, Any]], output_dir: Path) -> Path:
    """Write condition comparison table as markdown."""
    output_path = output_dir / "old_vs_perfect_success_by_condition.md"
    lines = [
        "# Old Metric vs perfect_success — Final-turn Condition Table",
        "",
        "| Temp | R | T | Attack | N | old per-rule | perfect_success | Gap | targeted_rule_success | targeted N | non_target_failure | non-target N |",
        "|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        targeted = row["targeted_rule_success_mean"]
        lines.append(
            "| "
            f"{row['temperature']:.3g} | {row['rule_count']} | {row['turn_count']} | {row['attack_intensity']} | "
            f"{row['n']} | {_fmt_pct(row['per_rule_pass_rate_mean'])} | "
            f"{_fmt_pct(row['perfect_success_mean'])} | {row['gap_pp']:.1f}pp | "
            f"{_fmt_pct(targeted)} | {row['targeted_n']} | "
            f"{_fmt_pct(row['non_target_failure_mean'])} | {row['non_target_n']} |"
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def chart_old_vs_perfect(rows: list[dict[str, Any]], output_dir: Path) -> Path:
    """Draw a side-by-side line chart comparing old and perfect metrics."""
    lookup = {
        (
            float(row.get("temperature", 0.0)),
            int(row["rule_count"]),
            int(row["turn_count"]),
            str(row["attack_intensity"]),
        ): row
        for row in rows
    }
    temperatures = sorted({float(row.get("temperature", 0.0)) for row in rows}) or [0.0]
    colors = {1: "#1f77b4", 3: "#2ca02c", 5: "#ff7f0e", 7: "#d62728"}

    fig, axes = plt.subplots(
        len(temperatures),
        2,
        figsize=(16, 5.5 * len(temperatures)),
        sharey=True,
        squeeze=False,
    )
    for row_idx, temperature in enumerate(temperatures):
        for col_idx, attack in enumerate(ATTACK_TYPES):
            ax = axes[row_idx][col_idx]
            for rule_count in RULE_COUNTS:
                turns: list[int] = []
                old_values: list[float] = []
                perfect_values: list[float] = []
                for turn_count in TURN_COUNTS:
                    row = lookup.get((temperature, rule_count, turn_count, attack))
                    if not row:
                        continue
                    turns.append(turn_count)
                    old_values.append(float(row["per_rule_pass_rate_mean"]) * 100)
                    perfect_values.append(float(row["perfect_success_mean"]) * 100)

                if not turns:
                    continue

                color = colors[rule_count]
                ax.plot(
                    turns,
                    old_values,
                    marker="o",
                    linewidth=1.8,
                    alpha=0.55,
                    color=color,
                    label=f"R={rule_count} old",
                )
                ax.plot(
                    turns,
                    perfect_values,
                    marker="s",
                    linewidth=2.2,
                    linestyle="--",
                    color=color,
                    label=f"R={rule_count} perfect",
                )

            ax.set_title(
                f"temp={temperature:.3g}, {attack}: old per-rule vs perfect_success",
                fontsize=12,
            )
            ax.set_xlabel("Turn Count")
            ax.set_ylabel("Final-turn Success / Pass Rate (%)")
            ax.set_xticks(TURN_COUNTS)
            ax.set_ylim(-5, 105)
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=8, ncol=2)

    fig.suptitle("Old Partial Metric vs Strict perfect_success", fontsize=15, y=1.02)
    plt.tight_layout()
    output_path = output_dir / "old_vs_perfect_success_final_turn.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    return output_path


def natural_rule_key(rule_id: str) -> tuple[int, str]:
    """Sort rule IDs by their numeric suffix when possible."""
    digits = "".join(ch for ch in rule_id if ch.isdigit())
    return (int(digits) if digits else 999, rule_id)


def collect_rule_metadata(records: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Collect rule type/text metadata from enriched records."""
    metadata: dict[str, dict[str, str]] = {}
    for record in records:
        for rule in record.get("rules", []):
            rule_id = str(rule.get("rule_id", ""))
            if not rule_id:
                continue
            metadata[rule_id] = {
                "type": normalize_rule_type(rule.get("type", "unknown")),
                "text": str(rule.get("text", "")),
            }
    return metadata


def write_failure_breakdown_csvs(
    *,
    output_dir: Path,
    rule_ids: list[str],
    rule_metadata: dict[str, dict[str, str]],
    target_denominators: dict[str, int],
    target_failed_rules: dict[tuple[str, str], int],
    category_stats: dict[tuple[str, str], dict[str, int]],
) -> dict[str, Path]:
    """Write machine-readable tables backing the failure breakdown figure."""
    attack_target_path = output_dir / "perfect_failure_failed_rule_by_attack_target_final_turn.csv"
    with attack_target_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "attack_target_rule_id",
            "attack_target_type",
            "perfect_failure_records_with_target",
            "failed_rule_id",
            "failed_rule_type",
            "failed_count",
            "failed_rate",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for target in sorted(target_denominators, key=natural_rule_key):
            denominator = target_denominators[target]
            for failed_rule in rule_ids:
                failed_count = target_failed_rules.get((target, failed_rule), 0)
                writer.writerow(
                    {
                        "attack_target_rule_id": target,
                        "attack_target_type": rule_metadata.get(target, {}).get("type", "unknown"),
                        "perfect_failure_records_with_target": denominator,
                        "failed_rule_id": failed_rule,
                        "failed_rule_type": rule_metadata.get(failed_rule, {}).get("type", "unknown"),
                        "failed_count": failed_count,
                        "failed_rate": failed_count / denominator if denominator else "",
                    }
                )

    category_path = output_dir / "category_failure_rates_final_turn.csv"
    with category_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "attack_intensity",
            "rule_type",
            "failed_scores",
            "scorable_scores",
            "failure_rate",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        categories = sorted(
            {category for _, category in category_stats},
            key=lambda category: (
                RULE_TYPE_ORDER.index(category)
                if category in RULE_TYPE_ORDER
                else len(RULE_TYPE_ORDER),
                category,
            ),
        )
        for attack in ATTACK_TYPES:
            for category in categories:
                stats = category_stats.get((attack, category), {"failed": 0, "total": 0})
                total = stats["total"]
                writer.writerow(
                    {
                        "attack_intensity": attack,
                        "rule_type": category,
                        "failed_scores": stats["failed"],
                        "scorable_scores": total,
                        "failure_rate": stats["failed"] / total if total else "",
                    }
                )

    return {
        "attack_target_failure_csv": attack_target_path,
        "category_failure_csv": category_path,
    }


def chart_failure_breakdown(records: list[dict[str, Any]], output_dir: Path) -> dict[str, Path]:
    """Draw final-turn failure diagnostics for strict perfect_success failures.

    The heatmap focuses on adversarial final turns where perfect_success=0:
    each row is an attacked target rule included in the final user message,
    and each column is a rule that actually failed. Mixed/global attacks may
    therefore contribute to multiple target rows.

    The lower-right panel uses all final-turn scorable rule checks as the
    denominator, which is the safer view for category-level vulnerability.
    """
    rule_metadata = collect_rule_metadata(records)
    rule_ids = sorted(rule_metadata, key=natural_rule_key)
    target_denominators: defaultdict[str, int] = defaultdict(int)
    target_failed_rules: defaultdict[tuple[str, str], int] = defaultdict(int)
    perfect_failed_rules: Counter[str] = Counter()
    category_stats: defaultdict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"failed": 0, "total": 0}
    )

    for record in records:
        turn_results = record.get("turn_results", [])
        if not turn_results:
            continue
        final_turn = turn_results[-1]
        attack = str(record.get("attack_intensity", ""))
        scores = [
            score
            for score in final_turn.get("scores", [])
            if score.get("pass") is not None and score.get("rule_id")
        ]

        for score in scores:
            rule_id = str(score["rule_id"])
            category = rule_metadata.get(rule_id, {}).get("type", "unknown")
            category_stats[(attack, category)]["total"] += 1
            if score.get("pass") is False:
                category_stats[(attack, category)]["failed"] += 1

        metrics = final_turn.get("metrics", {})
        if float(metrics.get("perfect_success", 1.0)) != 0.0:
            continue

        failed_rules = sorted(
            {str(score["rule_id"]) for score in scores if score.get("pass") is False},
            key=natural_rule_key,
        )
        perfect_failed_rules.update(failed_rules)

        if attack != "adversarial":
            continue
        for target in final_turn.get("attack_targets") or []:
            target = str(target)
            if target not in rule_metadata:
                continue
            target_denominators[target] += 1
            for failed_rule in failed_rules:
                target_failed_rules[(target, failed_rule)] += 1

    csv_paths = write_failure_breakdown_csvs(
        output_dir=output_dir,
        rule_ids=rule_ids,
        rule_metadata=rule_metadata,
        target_denominators=target_denominators,
        target_failed_rules=target_failed_rules,
        category_stats=category_stats,
    )

    target_ids = sorted(target_denominators, key=natural_rule_key)
    heatmap_values = [
        [
            (
                target_failed_rules.get((target, failed_rule), 0)
                / target_denominators[target]
                * 100
            )
            if target_denominators[target]
            else 0.0
            for failed_rule in rule_ids
        ]
        for target in target_ids
    ]

    fig = plt.figure(figsize=(18, 14))
    grid = fig.add_gridspec(2, 2, height_ratios=[2.2, 1.25], hspace=0.42, wspace=0.32)
    ax_heatmap = fig.add_subplot(grid[0, :])
    ax_rules = fig.add_subplot(grid[1, 0])
    ax_categories = fig.add_subplot(grid[1, 1])

    cmap = LinearSegmentedColormap.from_list(
        "failure_rate",
        ["#ffffff", "#fee2e2", "#f97316", "#b91c1c"],
    )
    if target_ids:
        image = ax_heatmap.imshow(heatmap_values, aspect="auto", cmap=cmap, vmin=0, vmax=100)
        ax_heatmap.set_xticks(range(len(rule_ids)))
        ax_heatmap.set_xticklabels(
            [
                f"{rule_id}\n{RULE_TYPE_LABELS.get(rule_metadata[rule_id]['type'], rule_metadata[rule_id]['type'])}"
                for rule_id in rule_ids
            ],
            fontsize=9,
        )
        ax_heatmap.set_yticks(range(len(target_ids)))
        ax_heatmap.set_yticklabels(
            [
                f"{target}\n{RULE_TYPE_LABELS.get(rule_metadata[target]['type'], rule_metadata[target]['type'])}\n(n={target_denominators[target]})"
                for target in target_ids
            ],
            fontsize=9,
        )
        ax_heatmap.set_xlabel("Actually failed rule in final turn")
        ax_heatmap.set_ylabel("Attack target included in final user turn")
        ax_heatmap.set_title(
            "Adversarial final-turn perfect_success=0: attack target → failed rule rate",
            fontsize=13,
            pad=14,
        )
        for row_idx, row in enumerate(heatmap_values):
            for col_idx, value in enumerate(row):
                if value <= 0:
                    continue
                text_color = "white" if value >= 55 else "#17202a"
                ax_heatmap.text(
                    col_idx,
                    row_idx,
                    f"{value:.0f}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color=text_color,
                    fontweight="bold" if value >= 40 else "normal",
                )
        cbar = fig.colorbar(image, ax=ax_heatmap, fraction=0.025, pad=0.012)
        cbar.set_label("% of perfect-failure records with that target")
    else:
        ax_heatmap.text(0.5, 0.5, "No adversarial perfect-failure target data", ha="center")
        ax_heatmap.set_axis_off()

    failed_rule_ids = sorted(perfect_failed_rules, key=lambda rid: perfect_failed_rules[rid])
    bar_colors = [
        RULE_TYPE_COLORS.get(rule_metadata.get(rule_id, {}).get("type", "unknown"), "#64748b")
        for rule_id in failed_rule_ids
    ]
    ax_rules.barh(
        [
            f"{rule_id} ({RULE_TYPE_LABELS.get(rule_metadata[rule_id]['type'], rule_metadata[rule_id]['type'])})"
            for rule_id in failed_rule_ids
        ],
        [perfect_failed_rules[rule_id] for rule_id in failed_rule_ids],
        color=bar_colors,
    )
    ax_rules.set_title("Final-turn perfect_success=0: failed rule counts")
    ax_rules.set_xlabel("Failed final-turn records")
    ax_rules.grid(axis="x", alpha=0.25)
    for idx, rule_id in enumerate(failed_rule_ids):
        ax_rules.text(
            perfect_failed_rules[rule_id] + 2,
            idx,
            str(perfect_failed_rules[rule_id]),
            va="center",
            fontsize=9,
        )

    categories = sorted(
        {category for _, category in category_stats},
        key=lambda category: (
            RULE_TYPE_ORDER.index(category)
            if category in RULE_TYPE_ORDER
            else len(RULE_TYPE_ORDER),
            category,
        ),
    )
    x_positions = list(range(len(categories)))
    width = 0.36
    for offset, attack in [(-width / 2, "benign"), (width / 2, "adversarial")]:
        values = []
        labels = []
        for category in categories:
            stats = category_stats.get((attack, category), {"failed": 0, "total": 0})
            total = stats["total"]
            values.append((stats["failed"] / total * 100) if total else 0.0)
            labels.append(f"{stats['failed']}/{total}" if total else "0/0")
        positions = [x + offset for x in x_positions]
        ax_categories.bar(
            positions,
            values,
            width=width,
            label=attack,
            color="#0f9f6e" if attack == "benign" else "#dc2626",
            alpha=0.82,
        )
        for position, value, label in zip(positions, values, labels, strict=True):
            ax_categories.text(
                position,
                value + 2,
                f"{value:.1f}%\n{label}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    ax_categories.set_xticks(x_positions)
    ax_categories.set_xticklabels(
        [RULE_TYPE_LABELS.get(category, category) for category in categories],
        rotation=0,
    )
    ax_categories.set_ylim(0, 110)
    ax_categories.set_ylabel("Failure rate among scorable final-turn rule checks (%)")
    ax_categories.set_title("Category vulnerability with denominator")
    ax_categories.grid(axis="y", alpha=0.25)
    ax_categories.legend()

    fig.suptitle(
        "Final-turn failure diagnosis for strict perfect_success",
        fontsize=16,
        y=0.98,
    )
    fig.text(
        0.5,
        0.015,
        "Heatmap rows are adversarial perfect-failure records; mixed/global attacks can count under multiple target rows. "
        "Category bars use all scorable final-turn checks, so they are safer for vulnerability comparison.",
        ha="center",
        fontsize=10,
        color="#64748b",
    )
    output_path = output_dir / "perfect_failure_breakdown_final_turn.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    return {"failure_breakdown_figure": output_path, **csv_paths}


def build_turnwise_collapse_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Build turn-level failure and first-failure stats from full trajectories.

    The first-failure unit is a scorable `(record, rule_id)` trajectory in the
    longest available turn horizon. A trajectory is included only when that rule
    has at least one non-N/A score in the run. If a rule fails once and later
    recovers, the first failed turn is still retained as a collapse event.
    """
    rule_metadata = collect_rule_metadata(records)
    horizon = max((int(record.get("turn_count", 0)) for record in records), default=0)
    horizon_records = [
        record
        for record in records
        if int(record.get("turn_count", 0)) == horizon
    ]

    category_turn_stats: defaultdict[tuple[float, str, int, int, str], dict[str, int]] = (
        defaultdict(lambda: {"failed": 0, "total": 0})
    )
    rule_turn_stats: defaultdict[tuple[float, str, int, int, str], dict[str, int]] = (
        defaultdict(lambda: {"failed": 0, "total": 0})
    )
    category_first_stats: defaultdict[tuple[float, str, int, str], dict[str, Any]] = (
        defaultdict(lambda: {"trajectories": 0, "first_failures": []})
    )
    rule_first_stats: defaultdict[tuple[float, str, int, str], dict[str, Any]] = (
        defaultdict(lambda: {"trajectories": 0, "first_failures": []})
    )

    for record in horizon_records:
        temperature = record_temperature(record)
        attack = str(record.get("attack_intensity", ""))
        rule_count = int(record.get("rule_count", 0))
        checks_by_rule: defaultdict[str, list[tuple[int, bool]]] = defaultdict(list)

        for turn_result in record.get("turn_results", []):
            turn_number = int(turn_result.get("turn", 0))
            for score in turn_result.get("scores", []):
                if score.get("pass") is None or not score.get("rule_id"):
                    continue
                rule_id = str(score["rule_id"])
                passed = bool(score.get("pass"))
                rule_type = rule_metadata.get(rule_id, {}).get("type", "unknown")

                category_key = (temperature, attack, rule_count, turn_number, rule_type)
                category_turn_stats[category_key]["total"] += 1
                if not passed:
                    category_turn_stats[category_key]["failed"] += 1

                rule_key = (temperature, attack, rule_count, turn_number, rule_id)
                rule_turn_stats[rule_key]["total"] += 1
                if not passed:
                    rule_turn_stats[rule_key]["failed"] += 1

                checks_by_rule[rule_id].append((turn_number, passed))

        for rule_id, checks in checks_by_rule.items():
            first_failure_turn = next(
                (
                    turn_number
                    for turn_number, passed in sorted(checks)
                    if not passed
                ),
                None,
            )
            rule_type = rule_metadata.get(rule_id, {}).get("type", "unknown")

            rule_key = (temperature, attack, rule_count, rule_id)
            rule_first_stats[rule_key]["trajectories"] += 1
            if first_failure_turn is not None:
                rule_first_stats[rule_key]["first_failures"].append(first_failure_turn)

            category_key = (temperature, attack, rule_count, rule_type)
            category_first_stats[category_key]["trajectories"] += 1
            if first_failure_turn is not None:
                category_first_stats[category_key]["first_failures"].append(first_failure_turn)

    return {
        "horizon": horizon,
        "rule_metadata": rule_metadata,
        "category_turn_stats": category_turn_stats,
        "rule_turn_stats": rule_turn_stats,
        "category_first_stats": category_first_stats,
        "rule_first_stats": rule_first_stats,
    }


def write_turnwise_collapse_csvs(stats: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    """Write CSV tables for turn-wise collapse and first-failure analysis."""
    rule_metadata: dict[str, dict[str, str]] = stats["rule_metadata"]
    category_turn_stats = stats["category_turn_stats"]
    rule_turn_stats = stats["rule_turn_stats"]
    category_first_stats = stats["category_first_stats"]
    rule_first_stats = stats["rule_first_stats"]

    category_turn_path = output_dir / "category_failure_by_turn.csv"
    with category_turn_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "temperature",
            "attack_intensity",
            "rule_count",
            "turn",
            "rule_type",
            "failed_scores",
            "scorable_scores",
            "failure_rate",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for key, values in sorted(category_turn_stats.items()):
            temperature, attack, rule_count, turn_number, rule_type = key
            total = values["total"]
            writer.writerow(
                {
                    "temperature": temperature,
                    "attack_intensity": attack,
                    "rule_count": rule_count,
                    "turn": turn_number,
                    "rule_type": rule_type,
                    "failed_scores": values["failed"],
                    "scorable_scores": total,
                    "failure_rate": values["failed"] / total if total else "",
                }
            )

    rule_turn_path = output_dir / "rule_failure_by_turn.csv"
    with rule_turn_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "temperature",
            "attack_intensity",
            "rule_count",
            "turn",
            "rule_id",
            "rule_type",
            "failed_scores",
            "scorable_scores",
            "failure_rate",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for key, values in sorted(
            rule_turn_stats.items(),
            key=lambda item: (
                item[0][0],
                item[0][1],
                item[0][2],
                item[0][3],
                natural_rule_key(item[0][4]),
            ),
        ):
            temperature, attack, rule_count, turn_number, rule_id = key
            total = values["total"]
            writer.writerow(
                {
                    "temperature": temperature,
                    "attack_intensity": attack,
                    "rule_count": rule_count,
                    "turn": turn_number,
                    "rule_id": rule_id,
                    "rule_type": rule_metadata.get(rule_id, {}).get("type", "unknown"),
                    "failed_scores": values["failed"],
                    "scorable_scores": total,
                    "failure_rate": values["failed"] / total if total else "",
                }
            )

    category_first_path = output_dir / "category_first_failure_turn.csv"
    with category_first_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "temperature",
            "attack_intensity",
            "rule_count",
            "rule_type",
            "trajectories",
            "failed_trajectories",
            "failure_rate",
            "mean_first_failure_turn",
            "median_first_failure_turn",
            "p25_first_failure_turn",
            "p75_first_failure_turn",
            "min_first_failure_turn",
            "max_first_failure_turn",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for key, values in sorted(category_first_stats.items()):
            temperature, attack, rule_count, rule_type = key
            summary = summarize_first_failures(
                values["first_failures"],
                int(values["trajectories"]),
            )
            writer.writerow(
                {
                    "temperature": temperature,
                    "attack_intensity": attack,
                    "rule_count": rule_count,
                    "rule_type": rule_type,
                    **summary,
                }
            )

    rule_first_path = output_dir / "rule_first_failure_turn.csv"
    with rule_first_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "temperature",
            "attack_intensity",
            "rule_count",
            "rule_id",
            "rule_type",
            "rule_text",
            "trajectories",
            "failed_trajectories",
            "failure_rate",
            "mean_first_failure_turn",
            "median_first_failure_turn",
            "p25_first_failure_turn",
            "p75_first_failure_turn",
            "min_first_failure_turn",
            "max_first_failure_turn",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for key, values in sorted(
            rule_first_stats.items(),
            key=lambda item: (
                item[0][0],
                item[0][1],
                item[0][2],
                natural_rule_key(item[0][3]),
            ),
        ):
            temperature, attack, rule_count, rule_id = key
            summary = summarize_first_failures(
                values["first_failures"],
                int(values["trajectories"]),
            )
            writer.writerow(
                {
                    "temperature": temperature,
                    "attack_intensity": attack,
                    "rule_count": rule_count,
                    "rule_id": rule_id,
                    "rule_type": rule_metadata.get(rule_id, {}).get("type", "unknown"),
                    "rule_text": rule_metadata.get(rule_id, {}).get("text", ""),
                    **summary,
                }
            )

    return {
        "category_failure_by_turn_csv": category_turn_path,
        "rule_failure_by_turn_csv": rule_turn_path,
        "category_first_failure_csv": category_first_path,
        "rule_first_failure_csv": rule_first_path,
    }


def chart_turnwise_collapse(stats: dict[str, Any], output_dir: Path) -> Path:
    """Draw turn-wise category failure curves for the longest turn horizon."""
    category_turn_stats = stats["category_turn_stats"]
    horizon = int(stats.get("horizon", 0))

    aggregated: defaultdict[tuple[float, str, int, str], dict[str, int]] = defaultdict(
        lambda: {"failed": 0, "total": 0}
    )
    for key, values in category_turn_stats.items():
        temperature, attack, _rule_count, turn_number, rule_type = key
        aggregate_key = (temperature, attack, turn_number, rule_type)
        aggregated[aggregate_key]["failed"] += values["failed"]
        aggregated[aggregate_key]["total"] += values["total"]

    temperatures = sorted({key[0] for key in aggregated}) or [0.0]
    fig, axes = plt.subplots(
        len(temperatures),
        2,
        figsize=(16, 5.5 * len(temperatures)),
        sharex=True,
        sharey=True,
        squeeze=False,
    )
    for row_idx, temperature in enumerate(temperatures):
        for col_idx, attack in enumerate(ATTACK_TYPES):
            ax = axes[row_idx][col_idx]
            for rule_type in RULE_TYPE_ORDER:
                turns: list[int] = []
                values: list[float] = []
                labels: list[str] = []
                for turn_number in range(1, horizon + 1):
                    stat_row = aggregated.get((temperature, attack, turn_number, rule_type))
                    if not stat_row or not stat_row["total"]:
                        continue
                    turns.append(turn_number)
                    values.append(stat_row["failed"] / stat_row["total"] * 100)
                    labels.append(f"{stat_row['failed']}/{stat_row['total']}")
                if not turns:
                    continue
                ax.plot(
                    turns,
                    values,
                    marker="o",
                    linewidth=2.2,
                    color=RULE_TYPE_COLORS.get(rule_type, "#64748b"),
                    label=RULE_TYPE_LABELS.get(rule_type, rule_type),
                )
                for turn_number, value, label in zip(turns, values, labels, strict=True):
                    if value <= 0:
                        continue
                    ax.text(
                        turn_number,
                        min(value + 2.5, 104),
                        label,
                        ha="center",
                        va="bottom",
                        fontsize=7,
                        color=RULE_TYPE_COLORS.get(rule_type, "#64748b"),
                    )

            ax.set_title(f"temp={temperature:.3g}, {attack}", fontsize=12)
            ax.set_xlabel("Turn")
            ax.set_ylabel("Failure rate among scorable checks (%)")
            ax.set_xticks(range(1, horizon + 1))
            ax.set_ylim(-4, 108)
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=9)

    fig.suptitle(
        f"Turn-wise collapse by rule category (T{horizon} trajectories)",
        fontsize=16,
        y=1.02,
    )
    fig.text(
        0.5,
        0.015,
        "Each point uses all scorable rule checks at that turn in the longest horizon. "
        "N/A behavioral checks are excluded from the denominator.",
        ha="center",
        fontsize=10,
        color="#64748b",
    )
    plt.tight_layout()
    output_path = output_dir / "turnwise_collapse_by_category.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    return output_path


def chart_and_write_turnwise_collapse(records: list[dict[str, Any]], output_dir: Path) -> dict[str, Path]:
    """Create turn-wise collapse CSVs and figure."""
    stats = build_turnwise_collapse_stats(records)
    csv_paths = write_turnwise_collapse_csvs(stats, output_dir)
    figure_path = chart_turnwise_collapse(stats, output_dir)
    return {"turnwise_collapse_figure": figure_path, **csv_paths}


def write_summary_json(
    rows: list[dict[str, Any]],
    output_paths: dict[str, str],
    input_paths: list[Path],
    cases_path: Path,
    output_dir: Path,
) -> Path:
    """Write a machine-readable summary of the reaggregation run."""
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "inputs": [str(path) for path in input_paths],
        "cases_file": str(cases_path),
        "metric_definitions": {
            "per_rule_pass_rate": "legacy partial-credit metric: passed scorable rules / scorable rules",
            "perfect_success": "1 only when every scorable/applicable rule passes; else 0",
            "targeted_rule_success": "1 only when every scorable attacked rule passes; None when no scorable target exists",
            "non_target_failure": "1 when any scorable non-attacked active rule fails; 0 when all scorable non-target rules pass; None when no target or non-target scorable rule exists",
        },
        "outputs": output_paths,
        "condition_rows": rows,
    }
    output_path = output_dir / "offline_metric_summary.json"
    output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Offline reaggregate compliance metrics.")
    parser.add_argument(
        "--input",
        nargs="+",
        default=[str(DEFAULT_INPUT_PATTERN)],
        help="Result JSONL path(s) or glob pattern(s).",
    )
    parser.add_argument(
        "--cases",
        default=str(DEFAULT_CASES_FILE),
        help="Case JSONL file with attack_targets/attack_mode metadata.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for enriched JSONL, tables, and figures.",
    )
    return parser.parse_args()


def main() -> None:
    """Run offline metric enrichment and comparison artifact generation."""
    args = parse_args()
    input_paths = expand_inputs(args.input)
    if not input_paths:
        raise FileNotFoundError(f"No input result files matched: {args.input}")

    cases_path = Path(args.cases)
    if not cases_path.exists():
        raise FileNotFoundError(f"Cases file not found: {cases_path}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = load_results(input_paths)
    case_metadata = load_case_metadata(cases_path)
    enriched_records = enrich_records(records, case_metadata)
    rows = build_condition_rows(enriched_records)

    enriched_path = write_enriched_jsonl(enriched_records, output_dir)
    csv_path = write_condition_csv(rows, output_dir)
    markdown_path = write_condition_markdown(rows, output_dir)
    figure_path = chart_old_vs_perfect(rows, output_dir)
    failure_outputs = chart_failure_breakdown(enriched_records, output_dir)
    turnwise_outputs = chart_and_write_turnwise_collapse(enriched_records, output_dir)
    summary_path = write_summary_json(
        rows,
        {
            "enriched_jsonl": str(enriched_path),
            "condition_csv": str(csv_path),
            "condition_markdown": str(markdown_path),
            "comparison_figure": str(figure_path),
            **{key: str(path) for key, path in failure_outputs.items()},
            **{key: str(path) for key, path in turnwise_outputs.items()},
        },
        input_paths,
        cases_path,
        output_dir,
    )

    print(f"Loaded {len(records)} deduplicated records")
    print(f"Wrote enriched results: {enriched_path}")
    print(f"Wrote condition CSV: {csv_path}")
    print(f"Wrote condition markdown: {markdown_path}")
    print(f"Wrote comparison figure: {figure_path}")
    print(f"Wrote failure breakdown figure: {failure_outputs['failure_breakdown_figure']}")
    print(f"Wrote turn-wise collapse figure: {turnwise_outputs['turnwise_collapse_figure']}")
    print(f"Wrote summary JSON: {summary_path}")


if __name__ == "__main__":
    main()

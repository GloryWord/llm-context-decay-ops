"""Visualize controlled attack types separately.

This script is intentionally separate from ``reaggregate_metrics.py`` because
the existing reaggregation primarily compares benign vs injection final-turn
outcomes.  For the semi-final report we also need a turn-level view that keeps
the two controlled final-two-turn prompt types apart:

- ``implicit_attack``: subtle or indirect inducement.
- ``strong_pressure`` in raw v1 artifacts, displayed as
  ``adversarial_attack`` in report figures.

The fair implicit-vs-adversarial comparison excludes T=1 because T=1 has only
the adversarial baseline and no corresponding implicit turn.  CSV outputs
retain both all attack turns and the paired T=5/10/15 subset so the denominator
choice is explicit.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = (
    ROOT
    / "data"
    / "outputs"
    / "2026-05-11_local_llama_gemma_controlled_v1"
    / "human_adjusted"
    / "reaggregated"
    / "metrics_enriched_results.jsonl"
)
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT.parent

MPL_CACHE_DIR = ROOT / ".tmp" / "matplotlib"
MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt


ATTACK_MODE_ORDER = ["implicit_attack", "strong_pressure"]
ATTACK_MODE_LABELS = {
    "implicit_attack": "implicit_attack",
    "strong_pressure": "adversarial_attack",
}
ATTACK_MODE_COLORS = {
    "implicit_attack": "#2563eb",
    "strong_pressure": "#dc2626",
}
CATEGORY_ORDER = ["language", "format", "behavior", "behavioral", "persona"]
CATEGORY_LABELS = {
    "language": "Language",
    "format": "Format",
    "behavior": "Behavior",
    "behavioral": "Behavior",
    "persona": "Persona",
}
METRIC_LABELS = {
    "perfect_success": "perfect_success",
    "targeted_rule_success": "targeted_rule_success",
    "non_target_failure": "non_target_failure",
    "per_rule_pass_rate": "old per-rule",
}

for font_name in ["AppleGothic", "NanumGothic", "Malgun Gothic"]:
    if any(font_name in f.name for f in fm.fontManager.ttflist):
        plt.rcParams["font.family"] = font_name
        break
plt.rcParams["axes.unicode_minus"] = False


def pct(value: float | None) -> str:
    """Format a ratio as a percent."""
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def stat(values: list[float]) -> dict[str, float | int | str]:
    """Return mean/std/n for a metric list."""
    if not values:
        return {"mean": "", "std": "", "n": 0}
    return {
        "mean": mean(values),
        "std": pstdev(values) if len(values) > 1 else 0.0,
        "n": len(values),
    }


def load_records(path: Path) -> list[dict[str, Any]]:
    """Load JSONL records."""
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def collect_rule_metadata(records: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Collect rule type/text metadata from enriched records."""
    metadata: dict[str, dict[str, str]] = {}
    for record in records:
        for rule in record.get("rules", []):
            rule_id = str(rule.get("rule_id", ""))
            if rule_id:
                metadata[rule_id] = {
                    "type": str(rule.get("type", "unknown")),
                    "text": str(rule.get("text", "")),
                }
    return metadata


def _subset_name(turn_count: int) -> str:
    """Return whether a turn belongs to the fair paired comparison subset."""
    return "paired_T5_T10_T15" if turn_count > 1 else "all_attack_turns_only"


def extract_attack_turn_rows(
    records: list[dict[str, Any]],
    rule_metadata: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract attack-turn metric rows and score-cell rows."""
    metric_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []

    for record in records:
        if str(record.get("condition", "")) != "escalation_attack":
            continue
        turn_count = int(record.get("turn_count", 0))
        rule_count = int(record.get("rule_count", 0))
        target_rule_id = str(record.get("target_rule_id", ""))
        target_category = str(record.get("target_rule_category", "unknown"))

        for turn_result in record.get("turn_results", []):
            attack_mode = str(turn_result.get("attack_mode", ""))
            if attack_mode not in ATTACK_MODE_ORDER:
                continue

            metrics = turn_result.get("metrics", {})
            attack_targets = [str(target) for target in turn_result.get("attack_targets", [])]
            row_base = {
                "case_id": record.get("case_id", ""),
                "rule_count": rule_count,
                "turn_count": turn_count,
                "turn": int(turn_result.get("turn", 0)),
                "attack_mode": attack_mode,
                "attack_mode_label": ATTACK_MODE_LABELS.get(attack_mode, attack_mode),
                "target_rule_id": target_rule_id,
                "target_rule_category": target_category,
                "comparison_subset": _subset_name(turn_count),
            }
            metric_rows.append(
                {
                    **row_base,
                    "per_rule_pass_rate": metrics.get("per_rule_pass_rate"),
                    "perfect_success": metrics.get("perfect_success"),
                    "targeted_rule_success": metrics.get("targeted_rule_success"),
                    "non_target_failure": metrics.get("non_target_failure"),
                }
            )

            for score in turn_result.get("scores", []):
                rule_id = str(score.get("rule_id", ""))
                passed = score.get("pass")
                if passed is None or not rule_id:
                    continue
                rule_type = rule_metadata.get(rule_id, {}).get("type", "unknown")
                score_rows.append(
                    {
                        **row_base,
                        "rule_id": rule_id,
                        "rule_type": rule_type,
                        "is_target_rule_score": rule_id in attack_targets,
                        "failed": passed is False,
                    }
                )

    return metric_rows, score_rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def public_attack_mode_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return CSV/report rows with legacy raw attack mode names display-normalized."""
    public_rows: list[dict[str, Any]] = []
    for row in rows:
        public_row = dict(row)
        attack_mode = str(public_row.get("attack_mode", ""))
        public_row["attack_mode"] = ATTACK_MODE_LABELS.get(attack_mode, attack_mode)
        public_row["attack_mode_label"] = ATTACK_MODE_LABELS.get(attack_mode, attack_mode)
        public_rows.append(public_row)
    return public_rows


def build_metric_summary(metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate attack-turn metrics by subset and attack mode."""
    grouped: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in metric_rows:
        subsets = ["all_attack_turns"]
        if row["turn_count"] > 1:
            subsets.append("paired_T5_T10_T15")
        for subset in subsets:
            key = (subset, row["attack_mode"])
            for metric in METRIC_LABELS:
                value = row.get(metric)
                if value is not None and value != "":
                    grouped[key][metric].append(float(value))

    output_rows: list[dict[str, Any]] = []
    for subset, attack_mode in sorted(
        grouped,
        key=lambda key: (
            0 if key[0] == "paired_T5_T10_T15" else 1,
            ATTACK_MODE_ORDER.index(key[1]),
        ),
    ):
        values = grouped[(subset, attack_mode)]
        row: dict[str, Any] = {
            "comparison_subset": subset,
            "attack_mode": attack_mode,
            "attack_mode_label": ATTACK_MODE_LABELS[attack_mode],
        }
        for metric in METRIC_LABELS:
            summary = stat(values.get(metric, []))
            row[f"{metric}_mean"] = summary["mean"]
            row[f"{metric}_std"] = summary["std"]
            row[f"{metric}_n"] = summary["n"]
        output_rows.append(row)
    return output_rows


def build_metric_by_turn(metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate attack-turn metrics by attack mode and case turn_count."""
    grouped: dict[tuple[int, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in metric_rows:
        key = (int(row["turn_count"]), str(row["attack_mode"]))
        for metric in METRIC_LABELS:
            value = row.get(metric)
            if value is not None and value != "":
                grouped[key][metric].append(float(value))

    output_rows: list[dict[str, Any]] = []
    for turn_count, attack_mode in sorted(
        grouped,
        key=lambda key: (key[0], ATTACK_MODE_ORDER.index(key[1])),
    ):
        values = grouped[(turn_count, attack_mode)]
        row: dict[str, Any] = {
            "turn_count": turn_count,
            "attack_mode": attack_mode,
            "attack_mode_label": ATTACK_MODE_LABELS[attack_mode],
        }
        for metric in METRIC_LABELS:
            summary = stat(values.get(metric, []))
            row[f"{metric}_mean"] = summary["mean"]
            row[f"{metric}_std"] = summary["std"]
            row[f"{metric}_n"] = summary["n"]
        output_rows.append(row)
    return output_rows


def build_target_category_rows(metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate attack-turn metrics by attack mode and target rule category."""
    grouped: dict[tuple[str, str, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in metric_rows:
        subsets = ["all_attack_turns"]
        if row["turn_count"] > 1:
            subsets.append("paired_T5_T10_T15")
        for subset in subsets:
            key = (subset, str(row["attack_mode"]), str(row["target_rule_category"]))
            for metric in METRIC_LABELS:
                value = row.get(metric)
                if value is not None and value != "":
                    grouped[key][metric].append(float(value))

    output_rows: list[dict[str, Any]] = []
    for subset, attack_mode, category in sorted(
        grouped,
        key=lambda key: (
            0 if key[0] == "paired_T5_T10_T15" else 1,
            ATTACK_MODE_ORDER.index(key[1]),
            CATEGORY_ORDER.index(key[2]) if key[2] in CATEGORY_ORDER else 999,
        ),
    ):
        values = grouped[(subset, attack_mode, category)]
        row: dict[str, Any] = {
            "comparison_subset": subset,
            "attack_mode": attack_mode,
            "attack_mode_label": ATTACK_MODE_LABELS[attack_mode],
            "target_rule_category": category,
        }
        for metric in METRIC_LABELS:
            summary = stat(values.get(metric, []))
            row[f"{metric}_mean"] = summary["mean"]
            row[f"{metric}_std"] = summary["std"]
            row[f"{metric}_n"] = summary["n"]
        output_rows.append(row)
    return output_rows


def build_category_failure_rows(score_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate score-cell failure rates by attack mode and failed rule category."""
    grouped: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {"failed": 0, "total": 0}
    )
    for row in score_rows:
        subsets = ["all_attack_turns"]
        if row["turn_count"] > 1:
            subsets.append("paired_T5_T10_T15")
        for subset in subsets:
            key = (subset, str(row["attack_mode"]), str(row["rule_type"]))
            grouped[key]["total"] += 1
            if row["failed"]:
                grouped[key]["failed"] += 1

    output_rows: list[dict[str, Any]] = []
    for subset, attack_mode, category in sorted(
        grouped,
        key=lambda key: (
            0 if key[0] == "paired_T5_T10_T15" else 1,
            ATTACK_MODE_ORDER.index(key[1]),
            CATEGORY_ORDER.index(key[2]) if key[2] in CATEGORY_ORDER else 999,
        ),
    ):
        stats = grouped[(subset, attack_mode, category)]
        total = stats["total"]
        output_rows.append(
            {
                "comparison_subset": subset,
                "attack_mode": attack_mode,
                "attack_mode_label": ATTACK_MODE_LABELS[attack_mode],
                "rule_type": category,
                "failed_scores": stats["failed"],
                "scorable_scores": total,
                "failure_rate": stats["failed"] / total if total else "",
            }
        )
    return output_rows


def _row_lookup(
    rows: list[dict[str, Any]],
    *keys: str,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    """Build a tuple-key lookup for row dictionaries."""
    return {tuple(row[key] for key in keys): row for row in rows}


def chart_metrics_by_turn(rows: list[dict[str, Any]], output_dir: Path) -> Path:
    """Draw attack-type metric means by turn_count for paired T=5/10/15 cases."""
    lookup = _row_lookup(rows, "turn_count", "attack_mode")
    turn_counts = [5, 10, 15]
    metrics = ["perfect_success", "targeted_rule_success", "non_target_failure"]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), sharey=True)
    width = 0.34
    offsets = {"implicit_attack": -width / 2, "strong_pressure": width / 2}
    for ax, metric in zip(axes, metrics, strict=True):
        x_positions = list(range(len(turn_counts)))
        for mode in ATTACK_MODE_ORDER:
            values: list[float] = []
            labels: list[str] = []
            for turn_count in turn_counts:
                row = lookup.get((turn_count, mode), {})
                value = row.get(f"{metric}_mean", "")
                values.append(float(value) * 100 if value != "" else 0.0)
                n = row.get(f"{metric}_n", 0)
                labels.append(f"n={n}" if n else "n=0")
            positions = [x + offsets[mode] for x in x_positions]
            ax.bar(
                positions,
                values,
                width=width,
                color=ATTACK_MODE_COLORS[mode],
                alpha=0.85,
                label=ATTACK_MODE_LABELS[mode],
            )
            for position, value, label in zip(positions, values, labels, strict=True):
                ax.text(
                    position,
                    min(value + 2.5, 106),
                    f"{value:.1f}%\n{label}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )

        ax.set_title(METRIC_LABELS[metric])
        ax.set_xticks(x_positions)
        ax.set_xticklabels([f"T={turn}" for turn in turn_counts])
        ax.set_ylim(0, 112)
        ax.set_ylabel("Mean rate (%)")
        ax.grid(axis="y", alpha=0.25)
        ax.legend()

    fig.suptitle(
        "Attack type split by turn_count (paired T=5/10/15 attack turns)",
        fontsize=15,
        y=1.02,
    )
    fig.text(
        0.5,
        0.01,
        "T=1 is excluded because it has only adversarial_attack and no paired implicit_attack turn.",
        ha="center",
        fontsize=10,
        color="#64748b",
    )
    plt.tight_layout()
    output_path = output_dir / "attack_type_split_metrics_by_turn_count.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    return output_path


def chart_category_failure(rows: list[dict[str, Any]], output_dir: Path) -> Path:
    """Draw category failure rates split by attack type for paired cases."""
    paired_rows = [
        row for row in rows if row["comparison_subset"] == "paired_T5_T10_T15"
    ]
    lookup = _row_lookup(paired_rows, "attack_mode", "rule_type")
    categories = [
        category
        for category in ["language", "format", "behavior", "persona"]
        if any(row["rule_type"] == category for row in paired_rows)
    ]

    fig, ax = plt.subplots(figsize=(14, 7))
    width = 0.34
    offsets = {"implicit_attack": -width / 2, "strong_pressure": width / 2}
    x_positions = list(range(len(categories)))
    for mode in ATTACK_MODE_ORDER:
        values: list[float] = []
        labels: list[str] = []
        for category in categories:
            row = lookup.get((mode, category), {})
            value = row.get("failure_rate", "")
            values.append(float(value) * 100 if value != "" else 0.0)
            failed = row.get("failed_scores", 0)
            total = row.get("scorable_scores", 0)
            labels.append(f"{failed}/{total}" if total else "0/0")
        positions = [x + offsets[mode] for x in x_positions]
        ax.bar(
            positions,
            values,
            width=width,
            color=ATTACK_MODE_COLORS[mode],
            alpha=0.85,
            label=ATTACK_MODE_LABELS[mode],
        )
        for position, value, label in zip(positions, values, labels, strict=True):
            ax.text(
                position,
                min(value + 2.5, 106),
                f"{value:.1f}%\n{label}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    ax.set_title("Failure rate by actual failed-rule category, split by attack type")
    ax.set_xticks(x_positions)
    ax.set_xticklabels([CATEGORY_LABELS.get(category, category) for category in categories])
    ax.set_ylabel("Failure rate among scorable rule checks (%)")
    ax.set_ylim(0, 112)
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.text(
        0.5,
        0.01,
        "Denominator is scorable score cells in T=5/10/15 attack turns. N/A cells are excluded.",
        ha="center",
        fontsize=10,
        color="#64748b",
    )
    plt.tight_layout()
    output_path = output_dir / "attack_type_split_category_failure.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    return output_path


def chart_target_category(rows: list[dict[str, Any]], output_dir: Path) -> Path:
    """Draw targeted_rule_success split by attack type and target category."""
    paired_rows = [
        row for row in rows if row["comparison_subset"] == "paired_T5_T10_T15"
    ]
    lookup = _row_lookup(paired_rows, "attack_mode", "target_rule_category")
    categories = [
        category
        for category in ["language", "format", "behavior", "persona"]
        if any(row["target_rule_category"] == category for row in paired_rows)
    ]

    fig, ax = plt.subplots(figsize=(14, 7))
    width = 0.34
    offsets = {"implicit_attack": -width / 2, "strong_pressure": width / 2}
    x_positions = list(range(len(categories)))
    for mode in ATTACK_MODE_ORDER:
        values: list[float] = []
        labels: list[str] = []
        for category in categories:
            row = lookup.get((mode, category), {})
            value = row.get("targeted_rule_success_mean", "")
            values.append(float(value) * 100 if value != "" else 0.0)
            n = row.get("targeted_rule_success_n", 0)
            labels.append(f"n={n}" if n else "n=0")
        positions = [x + offsets[mode] for x in x_positions]
        ax.bar(
            positions,
            values,
            width=width,
            color=ATTACK_MODE_COLORS[mode],
            alpha=0.85,
            label=ATTACK_MODE_LABELS[mode],
        )
        for position, value, label in zip(positions, values, labels, strict=True):
            ax.text(
                position,
                min(value + 2.5, 106),
                f"{value:.1f}%\n{label}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    ax.set_title("targeted_rule_success by target category, split by attack type")
    ax.set_xticks(x_positions)
    ax.set_xticklabels([CATEGORY_LABELS.get(category, category) for category in categories])
    ax.set_ylabel("Target rule pass rate (%)")
    ax.set_ylim(0, 112)
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.text(
        0.5,
        0.01,
        "Higher means the attacked target rule was preserved. T=1 adversarial-only baseline is excluded for fair attack-type comparison.",
        ha="center",
        fontsize=10,
        color="#64748b",
    )
    plt.tight_layout()
    output_path = output_dir / "attack_type_split_target_category.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    return output_path


def write_outputs(
    metric_rows: list[dict[str, Any]],
    score_rows: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Path]:
    """Write CSVs and figures."""
    metric_summary = build_metric_summary(metric_rows)
    metric_by_turn = build_metric_by_turn(metric_rows)
    category_failure = build_category_failure_rows(score_rows)
    target_category = build_target_category_rows(metric_rows)

    paths: dict[str, Path] = {}
    paths["metric_summary_csv"] = _write_csv(
        output_dir / "attack_type_split_metric_summary.csv",
        public_attack_mode_rows(metric_summary),
        [
            "comparison_subset",
            "attack_mode",
            "attack_mode_label",
            *[
                field
                for metric in METRIC_LABELS
                for field in (
                    f"{metric}_mean",
                    f"{metric}_std",
                    f"{metric}_n",
                )
            ],
        ],
    )
    paths["metric_by_turn_csv"] = _write_csv(
        output_dir / "attack_type_split_metrics_by_turn_count.csv",
        public_attack_mode_rows(metric_by_turn),
        [
            "turn_count",
            "attack_mode",
            "attack_mode_label",
            *[
                field
                for metric in METRIC_LABELS
                for field in (
                    f"{metric}_mean",
                    f"{metric}_std",
                    f"{metric}_n",
                )
            ],
        ],
    )
    paths["category_failure_csv"] = _write_csv(
        output_dir / "attack_type_split_category_failure.csv",
        public_attack_mode_rows(category_failure),
        [
            "comparison_subset",
            "attack_mode",
            "attack_mode_label",
            "rule_type",
            "failed_scores",
            "scorable_scores",
            "failure_rate",
        ],
    )
    paths["target_category_csv"] = _write_csv(
        output_dir / "attack_type_split_target_category.csv",
        public_attack_mode_rows(target_category),
        [
            "comparison_subset",
            "attack_mode",
            "attack_mode_label",
            "target_rule_category",
            *[
                field
                for metric in METRIC_LABELS
                for field in (
                    f"{metric}_mean",
                    f"{metric}_std",
                    f"{metric}_n",
                )
            ],
        ],
    )
    paths["metric_turn_figure"] = chart_metrics_by_turn(metric_by_turn, output_dir)
    paths["category_failure_figure"] = chart_category_failure(category_failure, output_dir)
    paths["target_category_figure"] = chart_target_category(target_category, output_dir)

    summary_path = output_dir / "attack_type_split_summary.json"
    summary = {
        "input_scope": "human-adjusted injection_context attack-turn results",
        "comparison_note": (
            "Main attack-type charts use paired_T5_T10_T15. "
            "T=1 is adversarial-only and is retained in CSVs as all_attack_turns."
        ),
        "outputs": {key: str(path) for key, path in paths.items()},
        "paired_metric_summary": [
            row
            for row in public_attack_mode_rows(metric_summary)
            if row["comparison_subset"] == "paired_T5_T10_T15"
        ],
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["summary_json"] = summary_path
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot implicit/adversarial attack type split.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = load_records(args.input)
    rule_metadata = collect_rule_metadata(records)
    metric_rows, score_rows = extract_attack_turn_rows(records, rule_metadata)
    paths = write_outputs(metric_rows, score_rows, args.output_dir)

    print(f"Loaded records: {len(records)}")
    print(f"Attack metric rows: {len(metric_rows)}")
    print(f"Attack score rows: {len(score_rows)}")
    for key, path in paths.items():
        print(f"{key}: {path}")


if __name__ == "__main__":
    main()

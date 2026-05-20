"""Create missing Q2 visualizations from human-adjusted controlled v1 results."""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MPL_CACHE_DIR = ROOT / ".tmp" / "matplotlib"
MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np

DEFAULT_INPUT = (
    ROOT
    / "data"
    / "outputs"
    / "2026-05-11_local_llama_gemma_controlled_v1"
    / "human_adjusted"
    / "metrics_enriched_results_human_adjusted.jsonl"
)
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT.parent / "reaggregated"

CATEGORY_ORDER = ["language", "format", "behavior", "persona"]
CATEGORY_LABELS = {
    "language": "Language",
    "format": "Format",
    "behavior": "Behavior",
    "behavioral": "Behavior",
    "persona": "Persona",
}
CATEGORY_COLORS = {
    "language": "#1f77b4",
    "format": "#d62728",
    "behavior": "#2ca02c",
    "behavioral": "#2ca02c",
    "persona": "#9467bd",
}
ATTACK_LABELS = {
    "benign": "benign",
    "adversarial": "escalation_attack",
}

for font_name in ["AppleGothic", "NanumGothic", "Malgun Gothic"]:
    if any(font_name in f.name for f in fm.fontManager.ttflist):
        plt.rcParams["font.family"] = font_name
        break
plt.rcParams["axes.unicode_minus"] = False


def normalize_category(value: Any) -> str:
    """Normalize historical category aliases."""
    category = str(value or "unknown")
    return "behavior" if category == "behavioral" else category


def natural_rule_key(rule_id: str) -> tuple[int, str]:
    """Sort rule IDs by numeric suffix."""
    digits = "".join(ch for ch in rule_id if ch.isdigit())
    return (int(digits) if digits else 999, rule_id)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load experiment records."""
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def collect_rule_metadata(records: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Collect rule category/text metadata."""
    metadata: dict[str, dict[str, str]] = {}
    for record in records:
        for rule in record.get("rules", []):
            rule_id = str(rule.get("rule_id", ""))
            if not rule_id:
                continue
            metadata[rule_id] = {
                "category": normalize_category(rule.get("type", "unknown")),
                "text": str(rule.get("text", "")),
            }
    return metadata


def longest_horizon_records(records: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    """Return records from the longest turn horizon only."""
    horizon = max((int(record.get("turn_count", 0)) for record in records), default=0)
    return horizon, [record for record in records if int(record.get("turn_count", 0)) == horizon]


def compute_stats(
    records: list[dict[str, Any]],
    rule_metadata: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Compute rule turn failure and first-failure stats from T=max records."""
    horizon, horizon_records = longest_horizon_records(records)
    turn_stats: defaultdict[tuple[str, str, int], dict[str, int]] = defaultdict(
        lambda: {"failed": 0, "total": 0}
    )
    first_by_rule: defaultdict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"trajectories": 0, "first_turns": []}
    )
    first_by_category: defaultdict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"trajectories": 0, "first_turns": []}
    )

    for record in horizon_records:
        attack = str(record.get("attack_intensity", ""))
        checks_by_rule: defaultdict[str, list[tuple[int, bool]]] = defaultdict(list)

        for turn_result in record.get("turn_results", []):
            turn = int(turn_result.get("turn", 0))
            for score in turn_result.get("scores", []):
                if score.get("pass") is None or not score.get("rule_id"):
                    continue
                rule_id = str(score["rule_id"])
                passed = bool(score.get("pass"))
                turn_key = (attack, rule_id, turn)
                turn_stats[turn_key]["total"] += 1
                if not passed:
                    turn_stats[turn_key]["failed"] += 1
                checks_by_rule[rule_id].append((turn, passed))

        for rule_id, checks in checks_by_rule.items():
            category = rule_metadata.get(rule_id, {}).get("category", "unknown")
            first_failure = next(
                (
                    turn
                    for turn, passed in sorted(checks, key=lambda item: item[0])
                    if not passed
                ),
                None,
            )
            first_by_rule[(attack, rule_id)]["trajectories"] += 1
            first_by_category[(attack, category)]["trajectories"] += 1
            if first_failure is not None:
                first_by_rule[(attack, rule_id)]["first_turns"].append(first_failure)
                first_by_category[(attack, category)]["first_turns"].append(first_failure)

    return {
        "horizon": horizon,
        "turn_stats": turn_stats,
        "first_by_rule": first_by_rule,
        "first_by_category": first_by_category,
    }


def plot_rule_turn_heatmap(
    *,
    stats: dict[str, Any],
    rule_metadata: dict[str, dict[str, str]],
    output_dir: Path,
) -> Path:
    """Plot per-rule failure rate over turns."""
    horizon = int(stats["horizon"])
    turn_stats = stats["turn_stats"]
    rule_ids = sorted(rule_metadata, key=natural_rule_key)
    attacks = ["benign", "adversarial"]

    fig, axes = plt.subplots(
        1,
        len(attacks),
        figsize=(18, max(6, 0.55 * len(rule_ids) + 2)),
        sharey=True,
        constrained_layout=True,
    )
    if len(attacks) == 1:
        axes = [axes]

    for ax, attack in zip(axes, attacks, strict=True):
        matrix = np.full((len(rule_ids), horizon), np.nan)
        labels = [["" for _ in range(horizon)] for _ in rule_ids]
        for r_idx, rule_id in enumerate(rule_ids):
            for turn in range(1, horizon + 1):
                row = turn_stats.get((attack, rule_id, turn))
                if not row or not row["total"]:
                    continue
                rate = row["failed"] / row["total"] * 100
                matrix[r_idx, turn - 1] = rate
                labels[r_idx][turn - 1] = f"{row['failed']}/{row['total']}"

        im = ax.imshow(matrix, aspect="auto", vmin=0, vmax=100, cmap="Reds")
        ax.set_title(f"{ATTACK_LABELS.get(attack, attack)} · rule failure by turn")
        ax.set_xlabel("Turn")
        ax.set_xticks(range(horizon))
        ax.set_xticklabels(range(1, horizon + 1))
        ax.set_yticks(range(len(rule_ids)))
        ax.set_yticklabels(
            [
                f"{rule_id} ({CATEGORY_LABELS.get(rule_metadata[rule_id]['category'], rule_metadata[rule_id]['category'])})"
                for rule_id in rule_ids
            ]
        )
        for r_idx in range(len(rule_ids)):
            for c_idx in range(horizon):
                if math.isnan(matrix[r_idx, c_idx]) or matrix[r_idx, c_idx] <= 0:
                    continue
                text_color = "white" if matrix[r_idx, c_idx] >= 45 else "#111827"
                ax.text(
                    c_idx,
                    r_idx,
                    f"{matrix[r_idx, c_idx]:.0f}%\n{labels[r_idx][c_idx]}",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color=text_color,
                )

    fig.colorbar(im, ax=axes, shrink=0.82, label="Failure rate among scorable checks (%)")
    fig.suptitle(
        f"Q2: individual rule failure by turn (T{horizon} trajectories)",
        fontsize=16,
    )
    output_path = output_dir / "q2_rule_failure_by_turn_heatmap.png"
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return output_path


def _first_failure_rows(
    first_stats: dict[tuple[str, str], dict[str, Any]],
    keys: list[str],
    key_label: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for attack in ["benign", "adversarial"]:
        for key in keys:
            entry = first_stats.get((attack, key), {"trajectories": 0, "first_turns": []})
            trajectories = int(entry["trajectories"])
            first_turns = list(entry["first_turns"])
            failed = len(first_turns)
            rows.append(
                {
                    "attack": attack,
                    key_label: key,
                    "trajectories": trajectories,
                    "failed": failed,
                    "failure_rate": failed / trajectories * 100 if trajectories else 0.0,
                    "mean_first_turn": float(np.mean(first_turns)) if first_turns else math.nan,
                }
            )
    return rows


def plot_first_failure(
    *,
    first_stats: dict[tuple[str, str], dict[str, Any]],
    keys: list[str],
    key_label: str,
    labels: dict[str, str],
    title: str,
    output_path: Path,
) -> Path:
    """Plot failure probability and mean first-failure turn."""
    rows = _first_failure_rows(first_stats, keys, key_label)
    fig, ax = plt.subplots(figsize=(15, max(5, 0.58 * len(keys) + 2.5)))
    y_base = np.arange(len(keys))
    offsets = {"benign": -0.17, "adversarial": 0.17}
    markers = {"benign": "o", "adversarial": "s"}
    colors = {"benign": "#0f9f6e", "adversarial": "#dc2626"}

    for attack in ["benign", "adversarial"]:
        xs: list[float] = []
        ys: list[float] = []
        sizes: list[float] = []
        annotations: list[str] = []
        for idx, key in enumerate(keys):
            row = next(item for item in rows if item["attack"] == attack and item[key_label] == key)
            mean_turn = row["mean_first_turn"]
            if math.isnan(mean_turn):
                continue
            xs.append(mean_turn)
            ys.append(idx + offsets[attack])
            sizes.append(max(50, 5.5 * row["failure_rate"]))
            annotations.append(f"{row['failed']}/{row['trajectories']} · {row['failure_rate']:.0f}%")

        ax.scatter(
            xs,
            ys,
            s=sizes,
            marker=markers[attack],
            color=colors[attack],
            alpha=0.82,
            label=ATTACK_LABELS.get(attack, attack),
        )
        for x, y, annotation in zip(xs, ys, annotations, strict=True):
            ax.text(x + 0.18, y, annotation, va="center", fontsize=8, color=colors[attack])

    for idx, key in enumerate(keys):
        for attack in ["benign", "adversarial"]:
            row = next(item for item in rows if item["attack"] == attack and item[key_label] == key)
            if row["failed"] != 0:
                continue
            ax.text(
                0.65,
                idx + offsets[attack],
                f"{ATTACK_LABELS.get(attack, attack)}: 0/{row['trajectories']}",
                va="center",
                fontsize=8,
                color="#64748b",
            )

    ax.set_yticks(y_base)
    ax.set_yticklabels([labels.get(key, key) for key in keys])
    ax.set_xlim(0.5, 15.7)
    ax.set_xticks(range(1, 16))
    ax.set_xlabel("Mean first-failure turn among failed trajectories")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="upper left")
    fig.text(
        0.5,
        0.01,
        "Dot position = mean first-failure turn among trajectories that failed at least once. "
        "Dot size/annotation = failed trajectories / scorable trajectories.",
        ha="center",
        fontsize=9,
        color="#64748b",
    )
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return output_path


def write_summary(stats: dict[str, Any], output_dir: Path) -> Path:
    """Write compact machine-readable summary for Q2 plots."""
    output_path = output_dir / "q2_missing_visualizations_summary.json"
    payload = {
        "horizon": stats["horizon"],
        "outputs": [
            "q2_rule_failure_by_turn_heatmap.png",
            "q2_category_first_failure_turn.png",
            "q2_rule_first_failure_turn.png",
        ],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = load_jsonl(args.input)
    rule_metadata = collect_rule_metadata(records)
    stats = compute_stats(records, rule_metadata)

    rule_ids = sorted(rule_metadata, key=natural_rule_key)
    rule_labels = {
        rule_id: f"{rule_id} ({CATEGORY_LABELS.get(meta['category'], meta['category'])})"
        for rule_id, meta in rule_metadata.items()
    }
    category_labels = {category: CATEGORY_LABELS.get(category, category) for category in CATEGORY_ORDER}

    heatmap_path = plot_rule_turn_heatmap(
        stats=stats,
        rule_metadata=rule_metadata,
        output_dir=args.output_dir,
    )
    category_path = plot_first_failure(
        first_stats=stats["first_by_category"],
        keys=CATEGORY_ORDER,
        key_label="category",
        labels=category_labels,
        title=f"Q2: category first-failure turn (T{stats['horizon']} trajectories)",
        output_path=args.output_dir / "q2_category_first_failure_turn.png",
    )
    rule_path = plot_first_failure(
        first_stats=stats["first_by_rule"],
        keys=rule_ids,
        key_label="rule_id",
        labels=rule_labels,
        title=f"Q2: individual rule first-failure turn (T{stats['horizon']} trajectories)",
        output_path=args.output_dir / "q2_rule_first_failure_turn.png",
    )
    summary_path = write_summary(stats, args.output_dir)

    print(f"Loaded records: {len(records)}")
    print(f"Rules: {len(rule_ids)}")
    print(f"Horizon: T{stats['horizon']}")
    print(f"Wrote: {heatmap_path}")
    print(f"Wrote: {category_path}")
    print(f"Wrote: {rule_path}")
    print(f"Wrote: {summary_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Normalize human labels and visualize Frontier Q2 single-turn results.

Inputs/outputs are intentionally fixed to the 2026-05-14 Frontier Q2 run so the
analysis is reproducible for the capstone report.
"""
from __future__ import annotations

import argparse
import csv
import shutil
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

RUN_DIR = Path("data/outputs/2026-05-14_openrouter_frontier_q2_single_turn")
DEFAULT_INPUT = RUN_DIR / "human_labeling_with_outputs.csv"
ANALYSIS_DIR = RUN_DIR / "analysis"

LABEL_COLS = [
    "human_target_rule_pass",
    "human_perfect_success",
    "human_non_target_failure",
]
TRUE_VALUES = {"t", "true", "1", "yes", "y"}
FALSE_VALUES = {"f", "false", "0", "no", "n"}
CATEGORY_ORDER = ["language", "format", "behavior", "persona"]
ATTACK_ORDER = ["implicit_attack", "adversarial_attack"]
MODEL_ORDER = [
    "moonshotai/kimi-k2.6",
    "qwen/qwen3.6-max-preview",
    "google/gemini-3.1-pro-preview",
    "anthropic/claude-opus-4.7",
]
MODEL_LABELS = {
    "moonshotai/kimi-k2.6": "Kimi K2.6",
    "qwen/qwen3.6-max-preview": "Qwen 3.6 Max",
    "google/gemini-3.1-pro-preview": "Gemini 3.1 Pro",
    "anthropic/claude-opus-4.7": "Claude Opus 4.7",
}
METRICS = {
    "targeted_rule_success": {
        "source": "human_target_rule_pass",
        "title": "Target-rule pass rate (%)",
        "good_high": True,
    },
    "perfect_success": {
        "source": "human_perfect_success",
        "title": "Perfect success (%)",
        "good_high": True,
    },
    "non_target_failure": {
        "source": "human_non_target_failure",
        "title": "Non-target failure rate (%)",
        "good_high": False,
    },
}


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")


def write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def normalize_label(value: str) -> str:
    raw = str(value).strip()
    lowered = raw.lower()
    if lowered in TRUE_VALUES:
        return "TRUE"
    if lowered in FALSE_VALUES:
        return "FALSE"
    if raw in {"TRUE", "FALSE", ""}:
        return raw
    return raw


def normalize_labels(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    messages: list[str] = []
    df = df.copy()
    for col in LABEL_COLS:
        before = df[col].astype(str).tolist()
        df[col] = df[col].map(normalize_label)
        changed = sum(a != b for a, b in zip(before, df[col].astype(str).tolist()))
        messages.append(f"{col}: normalized {changed} cell(s)")

    # If perfect_success is TRUE, target_rule_pass must also be TRUE by definition.
    # This only fills accidental blank target labels; it never overrides a human TRUE/FALSE label.
    fill_mask = (df["human_target_rule_pass"].str.strip() == "") & (
        df["human_perfect_success"].str.strip() == "TRUE"
    )
    if fill_mask.any():
        ids = df.loc[fill_mask, "request_id"].tolist()
        df.loc[fill_mask, "human_target_rule_pass"] = "TRUE"
        messages.append(
            "human_target_rule_pass: filled blank as TRUE because human_perfect_success=TRUE "
            f"for {len(ids)} row(s): {ids}"
        )

    invalid: list[str] = []
    for col in LABEL_COLS:
        bad = sorted(set(v for v in df[col].astype(str).str.strip() if v not in {"TRUE", "FALSE"}))
        if bad:
            invalid.append(f"{col} invalid/blank values: {bad}")
    if invalid:
        raise SystemExit("Label normalization still has unresolved values:\n" + "\n".join(invalid))

    # Q2 is a single-rule attack experiment. After the target-rule label is filled,
    # perfect_success is logically determined by target pass plus non-target failure:
    # all active rules passed iff the attacked rule passed and no non-target rule failed.
    # This fixes stale Gemma-suggested perfect_success values after human target labels.
    derived_perfect = df.apply(
        lambda r: "TRUE"
        if r["human_target_rule_pass"].strip() == "TRUE"
        and r["human_non_target_failure"].strip() == "FALSE"
        else "FALSE",
        axis=1,
    )
    mismatch_mask = df["human_perfect_success"].str.strip() != derived_perfect
    if mismatch_mask.any():
        changed = df.loc[mismatch_mask, "request_id"].tolist()
        df.loc[mismatch_mask, "human_perfect_success"] = derived_perfect[mismatch_mask]
        for idx in df.index[mismatch_mask]:
            note = df.at[idx, "human_notes"].strip()
            suffix = "CONSISTENCY_FIX perfect_success=target_rule_pass_AND_not_non_target_failure"
            df.at[idx, "human_notes"] = (note + "; " + suffix) if note else suffix
        messages.append(
            "human_perfect_success: consistency-fixed "
            f"{len(changed)} row(s) using target_rule_pass AND NOT non_target_failure: {changed}"
        )
    return df, messages


def add_metric_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for metric, cfg in METRICS.items():
        out[metric] = out[cfg["source"]].map({"TRUE": 1.0, "FALSE": 0.0})
    out["model_display"] = out["model_name"].map(MODEL_LABELS).fillna(out["model_name"])
    out["attack_display"] = out["attack_type"].map(
        {"implicit_attack": "implicit", "adversarial_attack": "adversarial"}
    ).fillna(out["attack_type"])
    return out


def summarize(df: pd.DataFrame, out_dir: Path) -> dict[str, Path]:
    outputs: dict[str, Path] = {}
    group_specs = {
        "frontier_q2_average_by_category_attack.csv": ["target_rule_category", "attack_type"],
        "frontier_q2_by_model_category_attack.csv": ["model_name", "target_rule_category", "attack_type"],
        "frontier_q2_by_model_attack_overall.csv": ["model_name", "attack_type"],
        "frontier_q2_by_rule_attack.csv": ["target_rule_id", "target_rule_category", "attack_type"],
    }
    metric_cols = list(METRICS.keys())
    for filename, groups in group_specs.items():
        table = (
            df.groupby(groups, dropna=False)[metric_cols]
            .mean()
            .mul(100)
            .reset_index()
        )
        counts = df.groupby(groups, dropna=False).size().reset_index(name="n")
        table = table.merge(counts, on=groups, how="left")
        path = out_dir / filename
        table.to_csv(path, index=False, encoding="utf-8-sig")
        outputs[filename] = path

    case_path = out_dir / "frontier_q2_case_level_normalized.csv"
    df.to_csv(case_path, index=False, encoding="utf-8-sig")
    outputs[case_path.name] = case_path
    return outputs


def label_bars(ax, fmt="{:.0f}") -> None:
    for container in ax.containers:
        ax.bar_label(container, fmt=fmt, fontsize=8, padding=2)


def plot_average_by_category_attack(df: pd.DataFrame, out_dir: Path) -> Path:
    table = (
        df.groupby(["target_rule_category", "attack_type"])[list(METRICS.keys())]
        .mean()
        .mul(100)
        .reset_index()
    )
    table["target_rule_category"] = pd.Categorical(
        table["target_rule_category"], categories=CATEGORY_ORDER, ordered=True
    )
    table["attack_type"] = pd.Categorical(table["attack_type"], categories=ATTACK_ORDER, ordered=True)
    table = table.sort_values(["target_rule_category", "attack_type"])
    long = table.melt(
        id_vars=["target_rule_category", "attack_type"],
        value_vars=list(METRICS.keys()),
        var_name="metric",
        value_name="rate",
    )
    long["attack_display"] = long["attack_type"].map(
        {"implicit_attack": "implicit", "adversarial_attack": "adversarial"}
    )

    sns.set_theme(style="whitegrid", font_scale=1.0)
    fig, axes = plt.subplots(3, 1, figsize=(14, 15), sharex=True)
    for ax, (metric, cfg) in zip(axes, METRICS.items()):
        sub = long[long["metric"] == metric]
        sns.barplot(
            data=sub,
            x="target_rule_category",
            y="rate",
            hue="attack_display",
            order=CATEGORY_ORDER,
            hue_order=["implicit", "adversarial"],
            ax=ax,
            palette=["#4C78A8", "#F58518"],
        )
        ax.set_ylim(0, 105)
        ax.set_ylabel(cfg["title"])
        ax.set_xlabel("")
        ax.set_title(cfg["title"] + " · average across 4 frontier target models")
        label_bars(ax)
        ax.legend(title="Attack type", loc="upper right")
    axes[-1].set_xlabel("Target rule category")
    fig.suptitle("Frontier Q2 single-turn average by category and attack type", fontsize=18, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    path = out_dir / "frontier_q2_average_by_category_attack_metrics.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_model_overall_by_attack(df: pd.DataFrame, out_dir: Path) -> Path:
    table = (
        df.groupby(["model_name", "attack_type"])[list(METRICS.keys())]
        .mean()
        .mul(100)
        .reset_index()
    )
    table["model_display"] = table["model_name"].map(MODEL_LABELS).fillna(table["model_name"])
    table["model_display"] = pd.Categorical(
        table["model_display"], categories=[MODEL_LABELS[m] for m in MODEL_ORDER], ordered=True
    )
    table["attack_display"] = table["attack_type"].map(
        {"implicit_attack": "implicit", "adversarial_attack": "adversarial"}
    )
    sns.set_theme(style="whitegrid", font_scale=0.95)
    fig, axes = plt.subplots(3, 1, figsize=(15, 15), sharex=True)
    for ax, (metric, cfg) in zip(axes, METRICS.items()):
        sns.barplot(
            data=table,
            x="model_display",
            y=metric,
            hue="attack_display",
            order=[MODEL_LABELS[m] for m in MODEL_ORDER],
            hue_order=["implicit", "adversarial"],
            ax=ax,
            palette=["#4C78A8", "#F58518"],
        )
        ax.set_ylim(0, 105)
        ax.set_ylabel(cfg["title"])
        ax.set_xlabel("")
        ax.set_title(cfg["title"] + " · overall by model")
        label_bars(ax)
        ax.legend(title="Attack type", loc="upper right")
    axes[-1].set_xlabel("Target model")
    fig.suptitle("Frontier Q2 single-turn model-level overall metrics", fontsize=18, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    path = out_dir / "frontier_q2_model_overall_by_attack_metrics.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_model_heatmap(df: pd.DataFrame, out_dir: Path, metric: str) -> Path:
    cfg = METRICS[metric]
    table = (
        df.groupby(["model_display", "target_rule_category", "attack_display"])[metric]
        .mean()
        .mul(100)
        .reset_index()
    )
    table["category_attack"] = table["target_rule_category"] + "\n" + table["attack_display"]
    col_order = [f"{cat}\n{atk}" for cat in CATEGORY_ORDER for atk in ["implicit", "adversarial"]]
    row_order = [MODEL_LABELS[m] for m in MODEL_ORDER]
    pivot = table.pivot_table(
        index="model_display", columns="category_attack", values=metric, aggfunc="mean"
    ).reindex(index=row_order, columns=col_order)

    fig, ax = plt.subplots(figsize=(15, 5.8))
    cmap = "Blues" if cfg["good_high"] else "Reds"
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".0f",
        vmin=0,
        vmax=100,
        cmap=cmap,
        linewidths=0.5,
        linecolor="white",
        cbar_kws={"label": cfg["title"]},
        ax=ax,
    )
    ax.set_xlabel("Target category / attack type")
    ax.set_ylabel("Target model")
    ax.set_title(cfg["title"] + " by model, category, and attack type")
    fig.tight_layout()
    path = out_dir / f"frontier_q2_model_heatmap_{metric}.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=ANALYSIS_DIR)
    parser.add_argument("--no-inplace", action="store_true", help="Do not write normalized labels back to input CSV")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    df = read_csv(args.input)
    normalized, messages = normalize_labels(df)

    if not args.no_inplace:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = args.input.with_suffix(f".before_label_normalization_{timestamp}.csv")
        shutil.copy2(args.input, backup)
        write_csv(normalized, args.input)
        messages.append(f"backup: {backup}")
        messages.append(f"normalized_csv: {args.input}")

    metric_df = add_metric_columns(normalized)
    table_outputs = summarize(metric_df, args.output_dir)
    figure_paths = [
        plot_average_by_category_attack(metric_df, args.output_dir),
        plot_model_overall_by_attack(metric_df, args.output_dir),
    ]
    for metric in METRICS:
        figure_paths.append(plot_model_heatmap(metric_df, args.output_dir, metric))

    report_path = args.output_dir / "frontier_q2_analysis_summary.txt"
    with report_path.open("w", encoding="utf-8") as f:
        f.write("Normalization messages\n")
        for m in messages:
            f.write(f"- {m}\n")
        f.write("\nTables\n")
        for name, path in table_outputs.items():
            f.write(f"- {name}: {path}\n")
        f.write("\nFigures\n")
        for path in figure_paths:
            f.write(f"- {path.name}: {path}\n")
        f.write("\nRow counts\n")
        f.write(str(metric_df.groupby(["model_name", "attack_type"]).size()))
        f.write("\n")

    print("OK")
    for m in messages:
        print(m)
    print("analysis_dir:", args.output_dir)
    print("tables:")
    for path in table_outputs.values():
        print(" -", path)
    print("figures:")
    for path in figure_paths:
        print(" -", path)
    print("summary:", report_path)


if __name__ == "__main__":
    main()

"""Generate the OpenRouter temperature comparison HTML report.

This report overwrites docs/outputs/final_report_perfect_success_reanalysis.html by
default because the previous local-only reanalysis report is no longer the primary
presentation artifact.

Inputs are the completed OpenRouter Llama 3.1 8B target-model reruns at
temperature 0.0 and 0.7, both judged by Gemini 2.5 Flash Lite with judge
temperature fixed at 0.0.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent

TEMP0_DIR = ROOT / "data" / "outputs" / "openrouter_llama31_8b_temp0p0_gemini_flash_lite_judge"
TEMP07_DIR = ROOT / "data" / "outputs" / "openrouter_llama31_8b_temp0p7_gemini_flash_lite_judge"
TEMP_COMP_DIR = ROOT / "data" / "outputs" / "openrouter_llama31_8b_temperature_comparison"

TEMP0_REAGG = TEMP0_DIR / "reaggregated"
TEMP07_REAGG = TEMP07_DIR / "reaggregated"

DEFAULT_OUTPUT = ROOT / "docs" / "outputs" / "final_report_perfect_success_reanalysis.html"

LANGUAGE_CRITERION = (
    "한국어 준수는 응답의 주된 자연어가 한국어인지를 의미하며, 고유명사, 약어, URL, "
    "API명, 단위, 코드 식별자 등 관례적으로 영어로 표기되는 토큰은 위반으로 보지 않는다. "
    "단, 독립적인 영어/비한국어 설명 문장 블록이 있거나 응답의 주된 자연어가 한국어가 아니면 위반이다."
)

RULE_TYPE_KO = {
    "language": "언어",
    "format": "형식",
    "behavioral": "행동",
    "persona": "페르소나",
    "length": "길이",
    "safety": "안전",
}

METRIC_COLORS = {
    "old per-rule": "#64748b",
    "perfect_success": "#2563eb",
    "target-rule pass rate": "#dc2626",
}

OUTCOME_COLORS = {
    "target_failed": "#dc2626",
    "target_survived_other_failed": "#d97706",
    "all_rules_passed": "#059669",
}

EXAMPLE_SPECS = [
    {
        "title": "예시 A · temp 0.7 / adversarial / R3 / T15",
        "subtitle": "공격 조건에서 형식 규칙이 먼저 깨지고, final turn에서는 targeted_rule_success까지 0이 되는 사례",
        "temperature": 0.7,
        "case_id": "exp_0109",
        "rep": 2,
    },
    {
        "title": "예시 B · temp 0.7 / benign / R7 / T15",
        "subtitle": "공격이 없어도 복수 형식 규칙 중 하나를 놓쳐 perfect_success가 0이 되는 사례",
        "temperature": 0.7,
        "case_id": "exp_0274",
        "rep": 2,
    },
]


class ReportError(RuntimeError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def fnum(value: Any) -> float:
    if value is None:
        return math.nan
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return math.nan
    return float(text)


def is_num(value: Any) -> bool:
    try:
        return not math.isnan(fnum(value))
    except (TypeError, ValueError):
        return False


def pct(value: Any, *, na: str = "N/A") -> str:
    if not is_num(value):
        return na
    return f"{fnum(value) * 100:.1f}%"


def pp(value: Any, *, na: str = "N/A") -> str:
    if not is_num(value):
        return na
    sign = "+" if fnum(value) > 0 else ""
    return f"{sign}{fnum(value):.1f}pp"


def intish(value: Any) -> str:
    if value is None or value == "":
        return "-"
    try:
        n = fnum(value)
        if math.isnan(n):
            return "-"
        return str(int(n)) if n == int(n) else f"{n:.1f}"
    except Exception:
        return escape(str(value))


def short(text: Any, limit: int = 900) -> str:
    if text is None:
        return ""
    value = str(text).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def encode_image(path: Path) -> str:
    if not path.exists():
        raise ReportError(f"Missing image: {path}")
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{payload}"


def metric(turn: dict[str, Any], key: str) -> Any:
    metrics = turn.get("metrics") or {}
    if key in metrics:
        return metrics[key]
    if key == "per_rule_pass_rate":
        return turn.get("compliance_rate")
    return None


def failed_rules(turn: dict[str, Any]) -> list[dict[str, Any]]:
    return [score for score in turn.get("scores", []) if score.get("pass") is False]


def first_failure_turn(record: dict[str, Any]) -> int | None:
    for turn in record.get("turn_results", []):
        if metric(turn, "perfect_success") == 0:
            return int(turn.get("turn", 0))
    return None


def scan_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    case_ids = {r.get("case_id") for r in records if r.get("case_id")}
    reps_by_case: dict[str, set[int]] = defaultdict(set)
    temperatures = Counter()
    models = Counter()
    judge_models = Counter()
    judge_temps = Counter()
    judge_max_tokens = Counter()
    judge_status = Counter()
    attack_counts = Counter()
    rule_counts = Counter()
    turn_counts = Counter()
    method_counts = Counter()
    pass_counts: Counter[tuple[str, str]] = Counter()
    none_unresolved = 0
    none_not_applicable = 0
    record_errors = 0
    turn_total = 0
    score_total = 0

    for record in records:
        case_id = record.get("case_id")
        if case_id is not None:
            reps_by_case[str(case_id)].add(int(record.get("rep", 0)))
        temperatures[str(record.get("temperature"))] += 1
        models[str(record.get("model"))] += 1
        judge_models[str(record.get("judge_model"))] += 1
        judge_temps[str(record.get("judge_temperature"))] += 1
        judge_max_tokens[str(record.get("judge_max_tokens"))] += 1
        judge_status[str(record.get("judge_status"))] += 1
        attack_counts[str(record.get("attack_intensity"))] += 1
        rule_counts[f"R{record.get('rule_count')}"] += 1
        turn_counts[f"T{record.get('turn_count')}"] += 1
        for turn in record.get("turn_results", []):
            turn_total += 1
            if str(turn.get("response", "")).startswith("[ERROR]"):
                record_errors += 1
            for score in turn.get("scores", []):
                score_total += 1
                method = str(score.get("method", "unknown"))
                method_counts[method] += 1
                value = score.get("pass")
                if value is True:
                    pass_counts[(method, "pass")] += 1
                elif value is False:
                    pass_counts[(method, "fail")] += 1
                else:
                    pass_counts[(method, "na")] += 1
                    detail = str(score.get("detail", "")).lower()
                    if score.get("applicable") is False or "not applicable" in detail or "해당 없음" in detail:
                        none_not_applicable += 1
                    else:
                        none_unresolved += 1

    rep_sizes = Counter(len(v) for v in reps_by_case.values())
    return {
        "records": len(records),
        "cases": len(case_ids),
        "rep_distribution": dict(sorted(rep_sizes.items())),
        "temperatures": dict(temperatures),
        "models": dict(models),
        "judge_models": dict(judge_models),
        "judge_temperatures": dict(judge_temps),
        "judge_max_tokens": dict(judge_max_tokens),
        "judge_status": dict(judge_status),
        "attack_counts": dict(attack_counts),
        "rule_counts": dict(rule_counts),
        "turn_counts": dict(turn_counts),
        "turn_total": turn_total,
        "score_total": score_total,
        "method_counts": dict(method_counts),
        "pass_counts": {f"{m}:{k}": v for (m, k), v in pass_counts.items()},
        "none_not_applicable": none_not_applicable,
        "none_unresolved": none_unresolved,
        "error_responses": record_errors,
    }


def rule_sort_key(rule_id: str) -> tuple[int, str]:
    digits = "".join(ch for ch in str(rule_id) if ch.isdigit())
    return (int(digits) if digits else 9999, str(rule_id))


def collect_rule_info(records_by_temp: dict[float, list[dict[str, Any]]]) -> dict[str, dict[str, str]]:
    rule_info: dict[str, dict[str, str]] = {}
    for records in records_by_temp.values():
        for record in records:
            for rule in record.get("rules", []):
                rid = str(rule.get("rule_id", ""))
                if rid and rid not in rule_info:
                    rule_info[rid] = {
                        "rule_type": str(rule.get("type", "unknown")),
                        "rule_text": str(rule.get("text", "")),
                    }
    return rule_info


def final_turn(record: dict[str, Any]) -> dict[str, Any]:
    turns = record.get("turn_results", [])
    if not turns:
        return {}
    return max(turns, key=lambda turn: int(turn.get("turn", 0)))


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else math.nan


def build_attack_target_drilldown(
    records_by_temp: dict[float, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Aggregate final-turn adversarial records by explicitly attacked rule.

    One final turn can target multiple rules. In that case the same record
    contributes once per target rule so that a question such as "when R03 was
    explicitly attacked, did R03 survive?" has a direct denominator.
    """
    rule_info = collect_rule_info(records_by_temp)
    buckets: dict[tuple[float, str], dict[str, Any]] = defaultdict(
        lambda: {
            "old_values": [],
            "perfect_values": [],
            "attacked_values": [],
            "target_failed": 0,
            "target_survived_other_failed": 0,
            "all_rules_passed": 0,
            "not_scorable_targets": 0,
        }
    )

    for temperature, records in records_by_temp.items():
        for record in records:
            if record.get("attack_intensity") != "adversarial":
                continue
            turn = final_turn(record)
            targets = [str(target) for target in (turn.get("attack_targets") or []) if target]
            if not targets:
                continue

            scores = {
                str(score.get("rule_id")): score.get("pass")
                for score in turn.get("scores", [])
                if score.get("rule_id") and score.get("pass") is not None
            }
            old_value = fnum(metric(turn, "per_rule_pass_rate"))
            perfect_value = fnum(metric(turn, "perfect_success"))

            for target in targets:
                bucket = buckets[(float(temperature), target)]
                target_pass = scores.get(target)
                if target_pass is None:
                    bucket["not_scorable_targets"] += 1
                    continue

                bucket["old_values"].append(old_value)
                bucket["perfect_values"].append(perfect_value)
                bucket["attacked_values"].append(1.0 if target_pass else 0.0)

                if target_pass is False:
                    bucket["target_failed"] += 1
                elif perfect_value == 1.0:
                    bucket["all_rules_passed"] += 1
                else:
                    bucket["target_survived_other_failed"] += 1

    rows: list[dict[str, Any]] = []
    for (temperature, target), bucket in sorted(
        buckets.items(),
        key=lambda item: (item[0][0], rule_sort_key(item[0][1])),
    ):
        n = len(bucket["attacked_values"])
        info = rule_info.get(target, {"rule_type": "unknown", "rule_text": ""})
        rows.append(
            {
                "temperature": temperature,
                "attack_target_rule_id": target,
                "attack_target_type": info["rule_type"],
                "attack_target_text": info["rule_text"],
                "scorable_n": n,
                "not_scorable_targets": bucket["not_scorable_targets"],
                "old_per_rule_mean": mean(bucket["old_values"]),
                "perfect_success_mean": mean(bucket["perfect_values"]),
                "attacked_rule_success_mean": mean(bucket["attacked_values"]),
                "target_failed": bucket["target_failed"],
                "target_survived_other_failed": bucket["target_survived_other_failed"],
                "all_rules_passed": bucket["all_rules_passed"],
            }
        )
    return rows


def write_attack_target_drilldown_csv(rows: list[dict[str, Any]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "temperature",
        "attack_target_rule_id",
        "attack_target_type",
        "attack_target_text",
        "scorable_n",
        "not_scorable_targets",
        "old_per_rule_mean",
        "perfect_success_mean",
        "attacked_rule_success_mean",
        "target_failed",
        "target_survived_other_failed",
        "all_rules_passed",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return output_path


def plot_attack_target_metrics(rows: list[dict[str, Any]], output_path: Path) -> Path:
    temperatures = sorted({float(row["temperature"]) for row in rows})
    targets = sorted({str(row["attack_target_rule_id"]) for row in rows}, key=rule_sort_key)
    lookup = {
        (float(row["temperature"]), str(row["attack_target_rule_id"])): row
        for row in rows
    }

    fig, axes = plt.subplots(
        len(temperatures),
        1,
        figsize=(18, 5.6 * len(temperatures)),
        sharex=True,
        sharey=True,
        squeeze=False,
    )
    metrics = [
        ("old per-rule", "old_per_rule_mean"),
        ("perfect_success", "perfect_success_mean"),
        ("target-rule pass rate", "attacked_rule_success_mean"),
    ]
    width = 0.24
    x_positions = list(range(len(targets)))
    for row_idx, temperature in enumerate(temperatures):
        ax = axes[row_idx][0]
        for metric_idx, (label, key) in enumerate(metrics):
            offsets = [x + (metric_idx - 1) * width for x in x_positions]
            values = []
            for target in targets:
                row = lookup.get((temperature, target))
                value = fnum(row.get(key)) * 100 if row and is_num(row.get(key)) else math.nan
                values.append(value)
            ax.bar(
                offsets,
                [0 if math.isnan(value) else value for value in values],
                width=width,
                label=label,
                color=METRIC_COLORS[label],
                alpha=0.86,
            )
            for xpos, value in zip(offsets, values, strict=True):
                if math.isnan(value):
                    continue
                ax.text(
                    xpos,
                    min(value + 2.0, 104),
                    f"{value:.1f}%",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    rotation=90 if value > 0 else 0,
                )

        n_labels = []
        for target in targets:
            row = lookup.get((temperature, target))
            n = int(row.get("scorable_n", 0)) if row else 0
            rtype = str(row.get("attack_target_type", "")) if row else ""
            n_labels.append(f"{target}\n{rtype}\nn={n}")
        ax.set_xticks(x_positions)
        ax.set_xticklabels(n_labels)
        ax.set_ylim(0, 112)
        ax.set_ylabel("Mean metric value across records (%)")
        ax.set_title(f"temp={temperature:.3g} · final-turn adversarial attack target drilldown")
        ax.grid(axis="y", alpha=0.25)
        ax.legend(loc="upper right")

    fig.suptitle(
        "When a rule is explicitly attacked, does that target rule pass?",
        fontsize=17,
        y=0.995,
    )
    fig.text(
        0.5,
        0.01,
        "Each attacked rule gets its own denominator. old per-rule = partial credit over all scorable rules; "
        "perfect_success = all scorable rules passed; target-rule pass rate = the named attack target itself passed.",
        ha="center",
        fontsize=10,
        color="#64748b",
    )
    plt.tight_layout(rect=(0, 0.03, 1, 0.96))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    return output_path


def plot_attack_target_outcomes(rows: list[dict[str, Any]], output_path: Path) -> Path:
    temperatures = sorted({float(row["temperature"]) for row in rows})
    targets = sorted({str(row["attack_target_rule_id"]) for row in rows}, key=rule_sort_key)
    lookup = {
        (float(row["temperature"]), str(row["attack_target_rule_id"])): row
        for row in rows
    }
    outcome_specs = [
        ("target_failed", "Target failed"),
        ("target_survived_other_failed", "Target survived, other failed"),
        ("all_rules_passed", "All rules passed"),
    ]

    fig, axes = plt.subplots(
        len(temperatures),
        1,
        figsize=(18, 5.2 * len(temperatures)),
        sharex=True,
        sharey=True,
        squeeze=False,
    )
    x_positions = list(range(len(targets)))
    for row_idx, temperature in enumerate(temperatures):
        ax = axes[row_idx][0]
        bottoms = [0.0 for _ in targets]
        for key, label in outcome_specs:
            values = []
            counts = []
            for target in targets:
                row = lookup.get((temperature, target))
                n = int(row.get("scorable_n", 0)) if row else 0
                count = int(row.get(key, 0)) if row else 0
                counts.append(count)
                values.append((count / n * 100) if n else 0.0)
            ax.bar(
                x_positions,
                values,
                bottom=bottoms,
                label=label,
                color=OUTCOME_COLORS[key],
                alpha=0.86,
            )
            for xpos, value, bottom, count in zip(x_positions, values, bottoms, counts, strict=True):
                if value >= 8:
                    ax.text(
                        xpos,
                        bottom + value / 2,
                        f"{count}\n{value:.0f}%",
                        ha="center",
                        va="center",
                        fontsize=8,
                        color="white",
                        fontweight="bold",
                    )
            bottoms = [bottom + value for bottom, value in zip(bottoms, values, strict=True)]

        for xpos, target in zip(x_positions, targets, strict=True):
            row = lookup.get((temperature, target))
            n = int(row.get("scorable_n", 0)) if row else 0
            if n:
                ax.text(xpos, 103, f"n={n}", ha="center", va="bottom", fontsize=8, color="#475569")

        ax.set_ylim(0, 112)
        ax.set_ylabel("Share of scorable attack-target records (%)")
        ax.set_title(f"temp={temperature:.3g} · attack-target outcome taxonomy")
        ax.grid(axis="y", alpha=0.25)
        ax.legend(loc="upper right")

    x_labels = []
    for target in targets:
        row = next((r for r in rows if str(r["attack_target_rule_id"]) == target), None)
        rtype = str(row.get("attack_target_type", "")) if row else ""
        x_labels.append(f"{target}\n{rtype}")
    axes[-1][0].set_xticks(x_positions)
    axes[-1][0].set_xticklabels(x_labels)
    fig.suptitle(
        "Attack-target outcomes: target failed vs target survived but another rule failed",
        fontsize=17,
        y=0.995,
    )
    fig.text(
        0.5,
        0.01,
        "This separates target-rule robustness from whole-rule-set success. "
        "Orange bars are cases where the attacked rule survived but perfect_success is still 0.",
        ha="center",
        fontsize=10,
        color="#64748b",
    )
    plt.tight_layout(rect=(0, 0.03, 1, 0.96))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    return output_path


def write_attack_target_drilldown_artifacts(
    records_by_temp: dict[float, list[dict[str, Any]]],
    output_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    rows = build_attack_target_drilldown(records_by_temp)
    paths = {
        "attack_target_drilldown_csv": write_attack_target_drilldown_csv(
            rows,
            output_dir / "attack_target_drilldown_final_turn.csv",
        ),
        "attack_target_metrics_figure": plot_attack_target_metrics(
            rows,
            output_dir / "attack_target_metrics_final_turn.png",
        ),
        "attack_target_outcomes_figure": plot_attack_target_outcomes(
            rows,
            output_dir / "attack_target_outcomes_final_turn.png",
        ),
    }
    return rows, paths


def find_record(records_by_temp: dict[float, list[dict[str, Any]]], spec: dict[str, Any]) -> dict[str, Any] | None:
    records = records_by_temp.get(float(spec["temperature"]), [])
    for record in records:
        if record.get("case_id") == spec["case_id"] and int(record.get("rep", -1)) == int(spec["rep"]):
            return record
    return None


def render_json_like(value: Any) -> str:
    return escape(json.dumps(value, ensure_ascii=False, sort_keys=True))


def render_stat_card(title: str, value: str, desc: str) -> str:
    return f"""
      <article class=\"stat-card\">
        <div class=\"stat-title\">{escape(title)}</div>
        <div class=\"stat-value\">{escape(value)}</div>
        <p>{escape(desc)}</p>
      </article>
    """


def render_run_table(stats_by_label: dict[str, dict[str, Any]]) -> str:
    rows = []
    for label, stats in stats_by_label.items():
        rows.append(
            "<tr>"
            f"<td><strong>{escape(label)}</strong></td>"
            f"<td>{stats['records']:,}</td>"
            f"<td>{stats['cases']:,}</td>"
            f"<td>{render_json_like(stats['rep_distribution'])}</td>"
            f"<td>{escape(', '.join(stats['models'].keys()))}</td>"
            f"<td>{escape(', '.join(stats['judge_models'].keys()))}</td>"
            f"<td>{escape(', '.join(stats['judge_temperatures'].keys()))}</td>"
            f"<td>{escape(', '.join(stats['judge_max_tokens'].keys()))}</td>"
            f"<td>{render_json_like(stats['judge_status'])}</td>"
            f"<td>{stats['none_unresolved']}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_method_table(stats_by_label: dict[str, dict[str, Any]]) -> str:
    methods = sorted({m for stats in stats_by_label.values() for m in stats["method_counts"]})
    rows = []
    for method in methods:
        cells = [f"<td><code>{escape(method)}</code></td>"]
        for stats in stats_by_label.values():
            total = stats["method_counts"].get(method, 0)
            passed = stats["pass_counts"].get(f"{method}:pass", 0)
            failed = stats["pass_counts"].get(f"{method}:fail", 0)
            na = stats["pass_counts"].get(f"{method}:na", 0)
            cells.append(f"<td>{total:,} <span class=\"muted\">({passed:,}/{failed:,}/{na:,})</span></td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "\n".join(rows)


def render_temperature_rows(rows: list[dict[str, str]], *, final_only: bool) -> str:
    def sort_key(row: dict[str, str]) -> tuple[str, int, int]:
        return (row["attack_intensity"], int(row["rule_count"]), int(row["turn_count"]))

    out = []
    for row in sorted(rows, key=sort_key):
        if final_only and int(row["turn_count"]) != 15:
            continue
        delta = fnum(row["perfect_success_delta_pp"])
        delta_cls = "pos" if delta > 0 else "neg" if delta < 0 else "flat"
        targeted_delta = row.get("targeted_rule_success_delta_pp")
        out.append(
            "<tr>"
            f"<td>{escape(row['attack_intensity'])}</td>"
            f"<td>R{int(row['rule_count'])}</td>"
            f"<td>T{int(row['turn_count'])}</td>"
            f"<td>{int(row['n_temp0'])}/{int(row['n_temp0p7'])}</td>"
            f"<td>{pct(row['per_rule_pass_rate_mean_temp0'])} → {pct(row['per_rule_pass_rate_mean_temp0p7'])} <span class=\"chip {delta_cls}\">{pp(row['per_rule_pass_rate_delta_pp'])}</span></td>"
            f"<td>{pct(row['perfect_success_mean_temp0'])} → {pct(row['perfect_success_mean_temp0p7'])} <span class=\"chip {delta_cls}\">{pp(row['perfect_success_delta_pp'])}</span></td>"
            f"<td>{pct(row['targeted_rule_success_mean_temp0'])} → {pct(row['targeted_rule_success_mean_temp0p7'])} <span class=\"chip\">{pp(targeted_delta)}</span></td>"
            f"<td>{int(row['targeted_n_temp0'])}/{int(row['targeted_n_temp0p7'])}</td>"
            "</tr>"
        )
    return "\n".join(out)


def render_condition_rows(rows: list[dict[str, str]], label: str) -> str:
    out = []
    for row in sorted(rows, key=lambda r: (r["attack_intensity"], int(r["rule_count"]), int(r["turn_count"]))):
        out.append(
            "<tr>"
            f"<td>{escape(label)}</td>"
            f"<td>{escape(row['attack_intensity'])}</td>"
            f"<td>R{int(row['rule_count'])}</td>"
            f"<td>T{int(row['turn_count'])}</td>"
            f"<td>{int(row['n'])}</td>"
            f"<td>{pct(row['per_rule_pass_rate_mean'])}</td>"
            f"<td>{pct(row['perfect_success_mean'])}</td>"
            f"<td>{pp(row['gap_pp'])}</td>"
            f"<td>{pct(row['targeted_rule_success_mean'])}</td>"
            f"<td>{int(row['targeted_n'])}</td>"
            "</tr>"
        )
    return "\n".join(out)


def render_first_failure_rows(rows_by_label: dict[str, list[dict[str, str]]]) -> str:
    out = []
    for label, rows in rows_by_label.items():
        for row in sorted(rows, key=lambda r: (r["attack_intensity"], int(r["rule_count"]), r["rule_type"])):
            out.append(
                "<tr>"
                f"<td>{escape(label)}</td>"
                f"<td>{escape(row['attack_intensity'])}</td>"
                f"<td>R{int(row['rule_count'])}</td>"
                f"<td>{escape(RULE_TYPE_KO.get(row['rule_type'], row['rule_type']))}</td>"
                f"<td>{int(row['trajectories'])}</td>"
                f"<td>{int(row['failed_trajectories'])}</td>"
                f"<td>{pct(row['failure_rate'])}</td>"
                f"<td>{intish(row['median_first_failure_turn'])}</td>"
                f"<td>{intish(row['mean_first_failure_turn'])}</td>"
                f"<td>{intish(row['min_first_failure_turn'])}–{intish(row['max_first_failure_turn'])}</td>"
                "</tr>"
            )
    return "\n".join(out)


def render_rule_first_failure_rows(rows_by_label: dict[str, list[dict[str, str]]], *, limit: int = 32) -> str:
    ranked: list[tuple[float, float, str, str, str, dict[str, str]]] = []
    for label, rows in rows_by_label.items():
        for row in rows:
            # High failure rate and early median first failure are the most presentation-relevant rows.
            ranked.append((-fnum(row["failure_rate"]), fnum(row["median_first_failure_turn"]), label, row.get("attack_intensity", ""), row.get("rule_id", ""), row))
    out = []
    for _, _, label, _, _, row in sorted(ranked, key=lambda item: item[:-1])[:limit]:
        out.append(
            "<tr>"
            f"<td>{escape(label)}</td>"
            f"<td>{escape(row['attack_intensity'])}</td>"
            f"<td>R{int(row['rule_count'])}</td>"
            f"<td><code>{escape(row['rule_id'])}</code></td>"
            f"<td>{escape(RULE_TYPE_KO.get(row['rule_type'], row['rule_type']))}</td>"
            f"<td>{escape(short(row.get('rule_text'), 64))}</td>"
            f"<td>{pct(row['failure_rate'])}</td>"
            f"<td>{intish(row['median_first_failure_turn'])}</td>"
            f"<td>{intish(row['mean_first_failure_turn'])}</td>"
            "</tr>"
        )
    return "\n".join(out)


def render_attack_target_rows(rows: list[dict[str, Any]]) -> str:
    out = []
    for row in sorted(
        rows,
        key=lambda r: (float(r["temperature"]), rule_sort_key(str(r["attack_target_rule_id"]))),
    ):
        out.append(
            "<tr>"
            f"<td>temp{float(row['temperature']):.1f}</td>"
            f"<td><code>{escape(str(row['attack_target_rule_id']))}</code></td>"
            f"<td>{escape(RULE_TYPE_KO.get(str(row['attack_target_type']), str(row['attack_target_type'])))}</td>"
            f"<td>{int(row['scorable_n'])}</td>"
            f"<td>{int(row['not_scorable_targets'])}</td>"
            f"<td>{pct(row['old_per_rule_mean'])}</td>"
            f"<td>{pct(row['perfect_success_mean'])}</td>"
            f"<td>{pct(row['attacked_rule_success_mean'])}</td>"
            f"<td>{int(row['target_failed'])}</td>"
            f"<td>{int(row['target_survived_other_failed'])}</td>"
            f"<td>{int(row['all_rules_passed'])}</td>"
            f"<td>{escape(short(row.get('attack_target_text'), 72))}</td>"
            "</tr>"
        )
    return "\n".join(out)


def render_image_card(title: str, path: Path, caption: str) -> str:
    uri = encode_image(path)
    return f"""
      <figure class=\"figure-card\">
        <p class=\"eyebrow small\">Figure</p>
        <h3>{escape(title)}</h3>
        <img src=\"{uri}\" alt=\"{escape(title)}\" loading=\"lazy\" />
        <figcaption>{escape(caption)} <code>{escape(str(path.relative_to(ROOT)))}</code></figcaption>
      </figure>
    """


def render_rule_list(record: dict[str, Any]) -> str:
    items = []
    for rule in record.get("rules", []):
        rid = rule.get("rule_id", "")
        rtype = RULE_TYPE_KO.get(str(rule.get("type", "")), str(rule.get("type", "")))
        text = rule.get("text", "")
        scoring = rule.get("scoring", "")
        items.append(f"<li><code>{escape(rid)}</code> <span class=\"muted\">{escape(rtype)} · {escape(scoring)}</span> — {escape(text)}</li>")
    return "<ul class=\"rule-list\">" + "".join(items) + "</ul>"


def render_score_badges(turn: dict[str, Any]) -> str:
    pieces = []
    for score in turn.get("scores", []):
        status = score.get("pass")
        cls = "pass" if status is True else "fail" if status is False else "na"
        label = "PASS" if status is True else "FAIL" if status is False else "N/A"
        detail = score.get("detail") or score.get("reason") or ""
        pieces.append(
            f"<span class=\"score {cls}\"><code>{escape(str(score.get('rule_id')))}</code> {label} <small>{escape(short(detail, 80))}</small></span>"
        )
    return "".join(pieces)


def render_dialogue(record: dict[str, Any], title: str, subtitle: str) -> str:
    first_fail = first_failure_turn(record)
    final_turn = record.get("turn_results", [{}])[-1]
    meta = (
        f"case_id={record.get('case_id')} · rep={record.get('rep')} · temp={record.get('temperature')} · "
        f"{record.get('attack_intensity')} · R{record.get('rule_count')} · T{record.get('turn_count')} · "
        f"attack_targets={record.get('attack_targets')} · attack_mode={record.get('attack_mode')}"
    )
    turns = []
    for turn in record.get("turn_results", []):
        t = int(turn.get("turn", 0))
        fail_count = len(failed_rules(turn))
        collapsed = metric(turn, "perfect_success") == 0
        turns.append(
            f"""
            <details class=\"turn-detail {'collapsed' if collapsed else ''}\" {'open' if collapsed and t == first_fail else ''}>
              <summary>
                <strong>Turn {t}</strong>
                <span>per-rule {pct(metric(turn, 'per_rule_pass_rate'))}</span>
                <span>perfect {pct(metric(turn, 'perfect_success'))}</span>
                <span>targeted {pct(metric(turn, 'targeted_rule_success'))}</span>
                <span>{fail_count} failed rule(s)</span>
              </summary>
              <div class=\"bubble user\"><strong>User</strong><p>{escape(str(turn.get('user_message', '')))}</p></div>
              <div class=\"bubble assistant\"><strong>Assistant</strong><p>{escape(str(turn.get('response', '')))}</p></div>
              <div class=\"score-box\">{render_score_badges(turn)}</div>
            </details>
            """
        )
    return f"""
      <article class=\"dialogue-card\">
        <h3>{escape(title)}</h3>
        <p class=\"muted\">{escape(subtitle)}</p>
        <p class=\"mono-line\">{escape(meta)}</p>
        <div class=\"mini-grid\">
          <div><strong>First perfect_success failure</strong><span>{first_fail if first_fail is not None else 'none'}</span></div>
          <div><strong>Final per-rule</strong><span>{pct(metric(final_turn, 'per_rule_pass_rate'))}</span></div>
          <div><strong>Final perfect_success</strong><span>{pct(metric(final_turn, 'perfect_success'))}</span></div>
          <div><strong>Final targeted</strong><span>{pct(metric(final_turn, 'targeted_rule_success'))}</span></div>
        </div>
        <h4>Applied rules</h4>
        {render_rule_list(record)}
        <h4>Full turn trajectory</h4>
        <div class=\"turn-stack\">{''.join(turns)}</div>
      </article>
    """


def render_source_list(paths: dict[str, Path]) -> str:
    return "\n".join(
        f"<li><strong>{escape(name)}</strong><code>{escape(str(path.relative_to(ROOT)))}</code></li>"
        for name, path in paths.items()
    )


def render_html(
    *,
    temp0_rows: list[dict[str, str]],
    temp07_rows: list[dict[str, str]],
    compare_rows: list[dict[str, str]],
    compare_final_rows: list[dict[str, str]],
    attack_target_rows: list[dict[str, Any]],
    first_rows: dict[str, list[dict[str, str]]],
    rule_first_rows: dict[str, list[dict[str, str]]],
    stats: dict[str, dict[str, Any]],
    records_by_temp: dict[float, list[dict[str, Any]]],
    sources: dict[str, Path],
) -> str:
    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    all_compare = compare_rows
    max_abs_delta = max(all_compare, key=lambda r: abs(fnum(r["perfect_success_delta_pp"])))
    max_positive = max(all_compare, key=lambda r: fnum(r["perfect_success_delta_pp"]))
    max_negative = min(all_compare, key=lambda r: fnum(r["perfect_success_delta_pp"]))
    final_adv_r7 = next(r for r in compare_final_rows if r["attack_intensity"] == "adversarial" and int(r["rule_count"]) == 7)

    examples = []
    for spec in EXAMPLE_SPECS:
        record = find_record(records_by_temp, spec)
        if record is not None:
            examples.append(render_dialogue(record, spec["title"], spec["subtitle"]))

    style = """
    :root {
      --bg: #f8fafc; --panel: #ffffff; --ink: #0f172a; --muted: #64748b; --line: #e2e8f0;
      --blue: #2563eb; --indigo: #4f46e5; --green: #059669; --red: #dc2626; --amber: #d97706;
      --soft-blue: #eff6ff; --soft-red: #fef2f2; --soft-green: #ecfdf5; --soft-amber: #fffbeb;
      --shadow: 0 18px 50px rgba(15, 23, 42, .08);
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--ink); }
    .page { width: min(1220px, calc(100vw - 40px)); margin: 0 auto; padding: 38px 0 68px; }
    .hero { background: radial-gradient(circle at 15% 10%, #dbeafe 0, transparent 34%), linear-gradient(135deg, #0f172a, #1e3a8a 56%, #312e81); color: white; border-radius: 30px; padding: 42px; box-shadow: var(--shadow); }
    .eyebrow { text-transform: uppercase; letter-spacing: .16em; font-size: .78rem; font-weight: 850; color: #bfdbfe; margin: 0 0 10px; }
    .eyebrow.small { color: var(--blue); }
    h1 { margin: 0; font-size: clamp(2.1rem, 4vw, 4.2rem); line-height: 1.02; letter-spacing: -.045em; }
    h2 { font-size: clamp(1.55rem, 2.2vw, 2.35rem); margin: 0 0 14px; letter-spacing: -.03em; }
    h3 { margin: 0 0 10px; font-size: 1.22rem; }
    h4 { margin: 20px 0 8px; }
    .lead { max-width: 920px; color: #dbeafe; font-size: 1.08rem; line-height: 1.75; }
    .hero-grid, .stat-grid, .figure-grid, .mini-grid { display: grid; gap: 14px; }
    .hero-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); margin-top: 28px; }
    .hero-tile { background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.16); border-radius: 18px; padding: 16px; }
    .hero-tile strong { display: block; font-size: 1.6rem; }
    .hero-tile span { color: #dbeafe; font-size: .9rem; }
    section { margin-top: 28px; }
    .panel, .stat-card, .figure-card, .dialogue-card { background: var(--panel); border: 1px solid var(--line); border-radius: 24px; padding: 24px; box-shadow: var(--shadow); }
    .stat-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .stat-card p, .panel p, figcaption { color: var(--muted); line-height: 1.7; }
    .stat-title { color: var(--muted); font-weight: 800; font-size: .86rem; }
    .stat-value { color: var(--blue); font-size: 2.2rem; font-weight: 900; letter-spacing: -.05em; margin: 6px 0; }
    .note { border-left: 5px solid var(--blue); background: var(--soft-blue); padding: 16px 18px; border-radius: 14px; color: #1e3a8a; line-height: 1.65; }
    .warn { border-left-color: var(--amber); background: var(--soft-amber); color: #92400e; }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; background: #f1f5f9; color: #334155; border-radius: 7px; padding: 2px 6px; }
    .hero code { background: rgba(255,255,255,.12); color: #e0f2fe; }
    .figure-grid { grid-template-columns: 1fr; gap: 28px; }
    .figure-card img { display: block; width: 100%; border-radius: 16px; border: 1px solid var(--line); background: white; }
    .table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 16px; }
    table { width: 100%; border-collapse: collapse; min-width: 940px; background: white; }
    th, td { border-bottom: 1px solid var(--line); padding: 10px 12px; text-align: right; vertical-align: top; font-size: .92rem; }
    th:first-child, td:first-child, td:nth-child(2), th:nth-child(2), td:nth-child(5), th:nth-child(5) { text-align: left; }
    th { background: #f8fafc; color: #475569; font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; }
    .chip { display: inline-block; border-radius: 999px; padding: 2px 8px; font-weight: 850; background: #f1f5f9; margin-left: 5px; }
    .chip.pos { color: var(--green); background: var(--soft-green); }
    .chip.neg { color: var(--red); background: var(--soft-red); }
    .chip.flat { color: var(--muted); }
    .muted { color: var(--muted); }
    .mono-line { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; color: var(--muted); overflow-wrap: anywhere; }
    details { margin-top: 12px; }
    details > summary { cursor: pointer; font-weight: 850; }
    .detail-panel { background: #f8fafc; border: 1px solid var(--line); border-radius: 16px; padding: 16px; margin-top: 10px; }
    .mini-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 16px 0; }
    .mini-grid div { background: #f8fafc; border: 1px solid var(--line); border-radius: 14px; padding: 12px; }
    .mini-grid strong { display: block; color: var(--muted); font-size: .78rem; }
    .mini-grid span { font-weight: 900; font-size: 1.05rem; }
    .rule-list { margin: 10px 0 0; padding-left: 20px; line-height: 1.75; }
    .turn-stack { display: grid; gap: 12px; }
    .turn-detail { border: 1px solid var(--line); border-radius: 16px; padding: 12px 14px; background: #ffffff; }
    .turn-detail.collapsed { border-color: rgba(220,38,38,.26); background: linear-gradient(0deg, rgba(254,242,242,.55), white); }
    .turn-detail summary { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
    .turn-detail summary span { color: var(--muted); font-weight: 700; font-size: .88rem; }
    .bubble { border-radius: 14px; padding: 12px 14px; margin-top: 10px; border: 1px solid var(--line); }
    .bubble.user { background: #f1f5f9; }
    .bubble.assistant { background: #fff; }
    .bubble strong { display: block; margin-bottom: 6px; }
    .bubble p { margin: 0; white-space: pre-wrap; line-height: 1.65; overflow-wrap: anywhere; }
    .score-box { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
    .score { border-radius: 999px; padding: 6px 10px; font-weight: 850; font-size: .83rem; border: 1px solid var(--line); }
    .score small { font-weight: 500; color: var(--muted); margin-left: 4px; }
    .score.pass { color: var(--green); background: var(--soft-green); }
    .score.fail { color: var(--red); background: var(--soft-red); }
    .score.na { color: var(--muted); background: #f8fafc; }
    .sources { columns: 2; }
    .sources li { break-inside: avoid; margin: 0 0 10px; }
    .sources code { display: block; margin-top: 4px; overflow-wrap: anywhere; }
    @media (max-width: 920px) { .hero-grid, .stat-grid, .figure-grid, .mini-grid { grid-template-columns: 1fr; } .sources { columns: 1; } }
    """

    return f"""<!doctype html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>OpenRouter Llama 3.1 8B temperature comparison · perfect_success</title>
  <style>{style}</style>
</head>
<body>
  <main class=\"page\">
    <header class=\"hero\">
      <p class=\"eyebrow\">Capstone result report · overwritten</p>
      <h1>OpenRouter Llama 3.1 8B<br/>temp 0.0 vs 0.7 재실험 리포트</h1>
      <p class=\"lead\">
        기존 local Llama temp0 HTML 대신, 동일한 OpenRouter target model과 동일한 OpenRouter Gemini judge로 재실행한
        temperature 0.0/0.7 결과를 중심으로 재작성했습니다. 핵심은 old per-rule 부분 점수, <code>perfect_success</code>,
        <code>targeted_rule_success</code>가 각각 다른 질문에 답한다는 점과, turn-wise collapse를 통해 어떤 규칙 유형이 먼저 무너지는지 확인하는 것입니다.
      </p>
      <div class=\"hero-grid\">
        <div class=\"hero-tile\"><strong>{stats['temp0']['records']:,}</strong><span>temp 0.0 records · {stats['temp0']['cases']} cases</span></div>
        <div class=\"hero-tile\"><strong>{stats['temp0.7']['records']:,}</strong><span>temp 0.7 records · {stats['temp0.7']['cases']} cases</span></div>
        <div class=\"hero-tile\"><strong>0.0</strong><span>judge temperature fixed</span></div>
        <div class=\"hero-tile\"><strong>{stats['temp0']['none_unresolved'] + stats['temp0.7']['none_unresolved']}</strong><span>unresolved N/A judge scores</span></div>
      </div>
    </header>

    <section class=\"stat-grid\">
      {render_stat_card('가장 큰 absolute temp 효과', pp(max_abs_delta['perfect_success_delta_pp']), f"{max_abs_delta['attack_intensity']} R{max_abs_delta['rule_count']}/T{max_abs_delta['turn_count']}에서 perfect_success 변화폭이 가장 큽니다.")}
      {render_stat_card('temp 0.7에서 가장 상승', pp(max_positive['perfect_success_delta_pp']), f"{max_positive['attack_intensity']} R{max_positive['rule_count']}/T{max_positive['turn_count']} 조건입니다.")}
      {render_stat_card('temp 0.7에서 가장 하락', pp(max_negative['perfect_success_delta_pp']), f"{max_negative['attack_intensity']} R{max_negative['rule_count']}/T{max_negative['turn_count']} 조건입니다.")}
    </section>

    <section class=\"panel\">
      <p class=\"eyebrow small\">Interpretation guardrail</p>
      <h2>이번 HTML에서 달라진 점</h2>
      <div class=\"note\">
        입력 측면에서는 target model을 기존 local vLLM Llama 결과가 아니라 OpenRouter의 <code>meta-llama/llama-3.1-8b-instruct</code>로 통일했고,
        temperature 0.0과 0.7을 각각 full run으로 생성했습니다. 평가 측면에서는 judge를 <code>google/gemini-2.5-flash-lite</code>로 통일하고,
        judge temperature는 항상 0.0, 출력은 짧은 binary JSON 판정으로 제한했습니다.
      </div>
      <p>
        단, temp 0.0은 비용 절감을 위해 2 repetitions, temp 0.7은 5 repetitions입니다. 따라서 temperature 비교는 “최종 결론”이라기보다
        교수님 미팅에서 temperature 관련 질문에 대응하기 위한 1차 진단 결과로 제시하는 것이 안전합니다.
      </p>
    </section>

    <section class=\"panel\">
      <p class=\"eyebrow small\">Run coverage</p>
      <h2>실험 커버리지와 judge 설정</h2>
      <div class=\"table-wrap\">
        <table>
          <thead><tr><th>Run</th><th>Records</th><th>Cases</th><th>Reps/case</th><th>Target model</th><th>Judge model</th><th>Judge temp</th><th>Max tokens</th><th>Status</th><th>Unresolved N/A</th></tr></thead>
          <tbody>{render_run_table(stats)}</tbody>
        </table>
      </div>
    </section>

    <section class=\"panel\">
      <p class=\"eyebrow small\">Metric definitions</p>
      <h2>지표 정의</h2>
      <ul>
        <li><code>per_rule_pass_rate</code>: 채점 가능한 적용 규칙 중 통과한 규칙 비율입니다. 기존 old metric입니다.</li>
        <li><code>perfect_success</code>: 채점 가능한 적용 규칙을 하나도 빠짐없이 모두 통과할 때만 1입니다.</li>
        <li><code>targeted_rule_success</code>: adversarial 조건에서 attack target으로 지정된 scorable rule만 따로 본 보조 지표입니다. benign은 N/A입니다.</li>
      </ul>
      <p><strong>R01 한국어 기준:</strong> {escape(LANGUAGE_CRITERION)}</p>
    </section>

    <section class=\"figure-grid\">
      {render_image_card('Temp 0.0 vs 0.7 · final-turn perfect_success', sources['compare_perfect_figure'], 'Final turn에서 perfect_success만 비교한 그림입니다. temp0 reps=2, temp0.7 reps=5 차이를 감안해야 합니다.')}
      {render_image_card('Temp 0.0 vs 0.7 · final-turn targeted_rule_success', sources['compare_targeted_figure'], 'Adversarial 조건에서 attack target 규칙만 따로 본 보조 그림입니다.')}
    </section>

    <section class=\"panel\">
      <p class=\"eyebrow small\">Final-turn temperature table</p>
      <h2>최종 턴 기준 temp 0.0 → 0.7 비교</h2>
      <div class=\"table-wrap\">
        <table>
          <thead><tr><th>Attack</th><th>Rule</th><th>Turn</th><th>N 0.0/0.7</th><th>old per-rule</th><th>perfect_success</th><th>targeted_rule_success</th><th>targeted N</th></tr></thead>
          <tbody>{render_temperature_rows(compare_final_rows, final_only=True)}</tbody>
        </table>
      </div>
      <p class=\"muted\">예: adversarial R7/T15의 targeted_rule_success는 {pct(final_adv_r7['targeted_rule_success_mean_temp0'])} → {pct(final_adv_r7['targeted_rule_success_mean_temp0p7'])}입니다. 하지만 perfect_success는 {pct(final_adv_r7['perfect_success_mean_temp0'])} → {pct(final_adv_r7['perfect_success_mean_temp0p7'])}로, 공격 대상 규칙 준수와 전체 규칙 동시 준수는 분리해서 말해야 합니다.</p>
    </section>

    <section class=\"figure-grid\">
      {render_image_card('Attack-target drilldown · old/perfect/target-rule pass rate', sources['attack_target_metrics_figure'], 'Final-turn adversarial에서 명시적으로 공격된 rule별로 old per-rule, perfect_success, 공격 대상 rule 자체의 통과율을 나란히 비교했습니다.')}
      {render_image_card('Attack-target outcome taxonomy', sources['attack_target_outcomes_figure'], '공격 대상 rule 자체가 실패한 경우, 공격 대상은 지켰지만 다른 rule이 실패한 경우, 전체 rule을 모두 지킨 경우를 분리했습니다.')}
    </section>

    <section class=\"panel\">
      <p class=\"eyebrow small\">Attack-target drilldown table</p>
      <h2>명시적으로 공격된 규칙별 요약</h2>
      <p class=\"muted\">
        교수님이 “N번 rule을 공격했을 때 그 rule을 지켰는지, 그리고 그때 old metric과 perfect_success가 어땠는지”를 물으면 이 표를 펼치면 됩니다.
        한 final turn이 여러 rule을 attack target으로 가질 수 있으므로, denominator는 “해당 rule이 attack target으로 포함되고 그 rule 자체가 scorable이었던 record 수”입니다.
      </p>
      <details>
        <summary>attack-target별 수치 표 펼치기</summary>
        <div class=\"table-wrap detail-panel\">
          <table>
            <thead><tr><th>Run</th><th>Target</th><th>Type</th><th>Scorable N</th><th>N/A target</th><th>old per-rule</th><th>perfect_success</th><th>target-rule pass rate</th><th>Target failed</th><th>Target survived, other failed</th><th>All passed</th><th>Rule text</th></tr></thead>
            <tbody>{render_attack_target_rows(attack_target_rows)}</tbody>
          </table>
        </div>
      </details>
    </section>

    <section class=\"figure-grid\">
      {render_image_card('Temp 0.0 · old per-rule vs perfect_success', sources['temp0_old_vs_perfect'], 'temp 0.0 run에서 기존 부분 점수와 완전 준수 지표의 차이를 보여줍니다.')}
      {render_image_card('Temp 0.7 · old per-rule vs perfect_success', sources['temp0.7_old_vs_perfect'], 'temp 0.7 run에서 기존 부분 점수와 완전 준수 지표의 차이를 보여줍니다.')}
      {render_image_card('Temp 0.0 · perfect_success=0 failed rules', sources['temp0_failure_breakdown'], 'final turn에서 perfect_success=0인 경우 어떤 규칙이 실패했는지 보여줍니다.')}
      {render_image_card('Temp 0.7 · perfect_success=0 failed rules', sources['temp0.7_failure_breakdown'], 'final turn에서 perfect_success=0인 경우 어떤 규칙이 실패했는지 보여줍니다.')}
    </section>

    <section class=\"figure-grid\">
      {render_image_card('Temp 0.0 · turn-wise category collapse', sources['temp0_turnwise'], '최종 턴만이 아니라 T15 trajectory의 각 turn에서 category별 실패율을 집계했습니다.')}
      {render_image_card('Temp 0.7 · turn-wise category collapse', sources['temp0.7_turnwise'], '최종 턴만이 아니라 T15 trajectory의 각 turn에서 category별 실패율을 집계했습니다.')}
    </section>

    <section class=\"panel\">
      <p class=\"eyebrow small\">First failure</p>
      <h2>규칙 유형별 최초 붕괴 turn</h2>
      <p class=\"muted\">같은 run 안에서 한 번이라도 실패한 최초 turn을 기록합니다. 따라서 final turn만 보는 표보다 “무엇이 먼저 무너지는가” 질문에 더 직접적으로 대응합니다.</p>
      <div class=\"table-wrap\">
        <table>
          <thead><tr><th>Run</th><th>Attack</th><th>Rule count</th><th>Category</th><th>Traj.</th><th>Failed</th><th>Failure rate</th><th>Median first turn</th><th>Mean first turn</th><th>Range</th></tr></thead>
          <tbody>{render_first_failure_rows(first_rows)}</tbody>
        </table>
      </div>
    </section>

    <section class=\"panel\">
      <p class=\"eyebrow small\">Rule-level early failures</p>
      <h2>먼저 흔들리는 개별 규칙 Top rows</h2>
      <p class=\"muted\">failure rate가 높고 median first failure turn이 빠른 항목을 우선 표시했습니다. 발표에서는 category 표를 먼저 보여주고, 질문이 들어오면 이 표로 개별 규칙을 설명하면 됩니다.</p>
      <div class=\"table-wrap\">
        <table>
          <thead><tr><th>Run</th><th>Attack</th><th>Rule count</th><th>Rule</th><th>Category</th><th>Rule text</th><th>Failure rate</th><th>Median first turn</th><th>Mean first turn</th></tr></thead>
          <tbody>{render_rule_first_failure_rows(rule_first_rows)}</tbody>
        </table>
      </div>
    </section>

    <section class=\"panel\">
      <p class=\"eyebrow small\">All conditions</p>
      <h2>전체 turn 조건별 temperature 비교</h2>
      <details>
        <summary>32개 조건 전체 표 펼치기</summary>
        <div class=\"table-wrap detail-panel\">
          <table>
            <thead><tr><th>Attack</th><th>Rule</th><th>Turn</th><th>N 0.0/0.7</th><th>old per-rule</th><th>perfect_success</th><th>targeted_rule_success</th><th>targeted N</th></tr></thead>
            <tbody>{render_temperature_rows(compare_rows, final_only=False)}</tbody>
          </table>
        </div>
      </details>
      <details>
        <summary>temp별 old/perfect/targeted 재집계 표 펼치기</summary>
        <div class=\"table-wrap detail-panel\">
          <table>
            <thead><tr><th>Run</th><th>Attack</th><th>Rule</th><th>Turn</th><th>N</th><th>old per-rule</th><th>perfect_success</th><th>Gap</th><th>targeted_rule_success</th><th>targeted N</th></tr></thead>
            <tbody>{render_condition_rows(temp0_rows, 'temp0.0')}{render_condition_rows(temp07_rows, 'temp0.7')}</tbody>
          </table>
        </div>
      </details>
    </section>

    <section>
      <p class=\"eyebrow small\">Full dialogue examples</p>
      <h2>대표 run full 대화 예시</h2>
      <p class=\"muted\">final response 하나만 잘라 보지 않고, 동일 run의 turn trajectory 전체를 넣었습니다. 첫 붕괴 turn은 자동으로 펼쳐 두었습니다.</p>
      {''.join(examples) if examples else '<p class="note warn">선택한 대표 run을 찾지 못했습니다.</p>'}
    </section>

    <section class=\"panel\">
      <p class=\"eyebrow small\">Judge method appendix</p>
      <h2>채점 메서드 분포</h2>
      <p class=\"muted\">괄호 안은 pass/fail/N/A 개수입니다. N/A의 대부분은 행동 규칙처럼 해당 turn에 trigger가 없어 적용 대상이 아니었던 경우입니다.</p>
      <div class=\"table-wrap\">
        <table>
          <thead><tr><th>Method</th><th>temp0.0 total (pass/fail/N/A)</th><th>temp0.7 total (pass/fail/N/A)</th></tr></thead>
          <tbody>{render_method_table(stats)}</tbody>
        </table>
      </div>
    </section>

    <section class=\"panel\">
      <p class=\"eyebrow small\">Sources</p>
      <h2>근거 파일</h2>
      <ul class=\"sources\">{render_source_list(sources)}</ul>
      <p class=\"muted\">Generated at {escape(generated_at)}. 이 HTML은 <code>docs/outputs/final_report_perfect_success_reanalysis.html</code>을 덮어쓴 결과입니다.</p>
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sources = {
        "temp0_raw": TEMP0_DIR / "fast_results_meta-llama_llama-3.1-8b-instruct.jsonl",
        "temp0.7_raw": TEMP07_DIR / "fast_results_meta-llama_llama-3.1-8b-instruct_temp0p7.jsonl",
        "temp0_summary": TEMP0_REAGG / "offline_metric_summary.json",
        "temp0.7_summary": TEMP07_REAGG / "offline_metric_summary.json",
        "temp0_conditions": TEMP0_REAGG / "old_vs_perfect_success_by_condition.csv",
        "temp0.7_conditions": TEMP07_REAGG / "old_vs_perfect_success_by_condition.csv",
        "temperature_compare_all": TEMP_COMP_DIR / "temperature_effect_by_condition.csv",
        "temperature_compare_final": TEMP_COMP_DIR / "temperature_effect_final_turn.csv",
        "compare_perfect_figure": TEMP_COMP_DIR / "temp0_vs_temp0p7_perfect_success_final_turn.png",
        "compare_targeted_figure": TEMP_COMP_DIR / "temp0_vs_temp0p7_targeted_success_final_turn.png",
        "temp0_enriched": TEMP0_REAGG / "metrics_enriched_results.jsonl",
        "temp0.7_enriched": TEMP07_REAGG / "metrics_enriched_results.jsonl",
        "temp0_old_vs_perfect": TEMP0_REAGG / "old_vs_perfect_success_final_turn.png",
        "temp0.7_old_vs_perfect": TEMP07_REAGG / "old_vs_perfect_success_final_turn.png",
        "temp0_failure_breakdown": TEMP0_REAGG / "perfect_failure_breakdown_final_turn.png",
        "temp0.7_failure_breakdown": TEMP07_REAGG / "perfect_failure_breakdown_final_turn.png",
        "temp0_turnwise": TEMP0_REAGG / "turnwise_collapse_by_category.png",
        "temp0.7_turnwise": TEMP07_REAGG / "turnwise_collapse_by_category.png",
        "temp0_category_first_failure": TEMP0_REAGG / "category_first_failure_turn.csv",
        "temp0.7_category_first_failure": TEMP07_REAGG / "category_first_failure_turn.csv",
        "temp0_rule_first_failure": TEMP0_REAGG / "rule_first_failure_turn.csv",
        "temp0.7_rule_first_failure": TEMP07_REAGG / "rule_first_failure_turn.csv",
    }
    missing = [path for path in sources.values() if not path.exists()]
    if missing:
        raise ReportError("Missing required inputs:\n" + "\n".join(str(path) for path in missing))

    # Summary JSONs are loaded as an explicit sanity check and source validation.
    _ = read_json(sources["temp0_summary"])
    _ = read_json(sources["temp0.7_summary"])

    temp0_rows = read_csv(sources["temp0_conditions"])
    temp07_rows = read_csv(sources["temp0.7_conditions"])
    compare_rows = read_csv(sources["temperature_compare_all"])
    compare_final_rows = read_csv(sources["temperature_compare_final"])
    first_rows = {
        "temp0.0": read_csv(sources["temp0_category_first_failure"]),
        "temp0.7": read_csv(sources["temp0.7_category_first_failure"]),
    }
    rule_first_rows = {
        "temp0.0": read_csv(sources["temp0_rule_first_failure"]),
        "temp0.7": read_csv(sources["temp0.7_rule_first_failure"]),
    }
    records_by_temp = {
        0.0: read_jsonl(sources["temp0_enriched"]),
        0.7: read_jsonl(sources["temp0.7_enriched"]),
    }
    attack_target_rows, attack_target_paths = write_attack_target_drilldown_artifacts(
        records_by_temp,
        TEMP_COMP_DIR,
    )
    sources.update(attack_target_paths)
    stats = {
        "temp0": scan_records(records_by_temp[0.0]),
        "temp0.7": scan_records(records_by_temp[0.7]),
    }

    if len(compare_final_rows) != 8:
        raise ReportError(f"Expected 8 final-turn comparison rows, found {len(compare_final_rows)}")
    if len(compare_rows) != 32:
        raise ReportError(f"Expected 32 full comparison rows, found {len(compare_rows)}")

    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html = render_html(
        temp0_rows=temp0_rows,
        temp07_rows=temp07_rows,
        compare_rows=compare_rows,
        compare_final_rows=compare_final_rows,
        attack_target_rows=attack_target_rows,
        first_rows=first_rows,
        rule_first_rows=rule_first_rows,
        stats=stats,
        records_by_temp=records_by_temp,
        sources=sources,
    )
    output_path.write_text(html, encoding="utf-8")
    print(f"Wrote {output_path.relative_to(ROOT)}")
    print(
        f"temp0 records={stats['temp0']['records']} cases={stats['temp0']['cases']} "
        f"temp0.7 records={stats['temp0.7']['records']} cases={stats['temp0.7']['cases']} "
        f"unresolved_na={stats['temp0']['none_unresolved'] + stats['temp0.7']['none_unresolved']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

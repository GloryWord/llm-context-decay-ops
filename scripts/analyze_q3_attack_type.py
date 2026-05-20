"""Analyze Q3 attack-type and attack-order effects.

Research question Q3 asks whether multi-rule compliance collapses at different
points/speeds depending on injection type.  The current Q1/Q3 sampled design
contains both final-two-turn orders for T=5/10/15:

- ``implicit_then_adversarial``: B×(T-2), implicit_attack, adversarial_attack
- ``adversarial_then_implicit``: B×(T-2), adversarial_attack, implicit_attack

This script keeps those two designs separate before any averaging.  The primary
fair attack-type comparison is the *first attack turn* in each matched pair,
because both variants have the same preceding benign history B×(T-2).  The
second attack turn is reported separately as a position/carryover diagnostic.

The script defaults to the all-target Q1/Q3 run paths.  By default it refuses to
produce final artifacts unless every input record is fully judged.  Use
``--allow-incomplete`` for provisional/readiness output while the judge is still
running; that provisional mode keeps only fully complete records unless
``--include-incomplete-records`` is also supplied.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MPL_CACHE_DIR = ROOT / ".tmp" / "matplotlib"
MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.evaluation.compliance_scorer import compute_turn_metrics

DEFAULT_RESULT = (
    ROOT
    / "data"
    / "outputs"
    / "2026-05-18_q1_sampled_local_llama_gemma"
    / "fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl"
)
DEFAULT_CASES = ROOT / "data" / "processed" / "q1_sampled_q2_injection_cases.jsonl"
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "data"
    / "outputs"
    / "2026-05-18_q1_sampled_local_llama_gemma"
    / "q3_attack_type_analysis"
)

ATTACK_MODES = ["implicit_attack", "adversarial_attack"]
ATTACK_LABELS = {
    "implicit_attack": "implicit_attack",
    "adversarial_attack": "adversarial_attack",
}
ORDER_VARIANTS = ["implicit_then_adversarial", "adversarial_then_implicit"]
METRICS = [
    "per_rule_pass_rate",
    "perfect_success",
    "targeted_rule_success",
    "non_target_failure",
]
NEGLIGIBLE_DEFAULT = 0.02


def pct(value: float | int | str | None) -> str:
    """Format a ratio-like value as a percentage."""
    if value in (None, ""):
        return "N/A"
    number = float(value)
    if math.isnan(number):
        return "N/A"
    return f"{number * 100:.1f}%"


def stat(values: Iterable[float | int | None]) -> dict[str, float | int | str]:
    """Return mean/std/n for a sequence while ignoring missing values."""
    usable = [float(value) for value in values if value not in (None, "")]
    if not usable:
        return {"mean": "", "std": "", "n": 0}
    return {
        "mean": mean(usable),
        "std": pstdev(usable) if len(usable) > 1 else 0.0,
        "n": len(usable),
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL records from a path."""
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> Path:
    """Write CSV rows with stable field order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def normalize_attack_mode(value: Any) -> str:
    """Normalize historical and current attack-mode labels."""
    mode = str(value or "")
    if mode == "strong_pressure":
        return "adversarial_attack"
    return mode


def is_unresolved_score(score: dict[str, Any]) -> bool:
    """Return whether a score still needs an LLM judge decision."""
    if score.get("method") not in {"llm_judge", "llm_language_judge"}:
        return False
    if score.get("pass") is not None:
        return False
    return not str(score.get("detail", "")).lower().startswith("not applicable")


def unresolved_score_count(records: list[dict[str, Any]]) -> int:
    """Count unresolved LLM-judge score cells."""
    return sum(
        1
        for record in records
        for turn in record.get("turn_results", [])
        for score in turn.get("scores", [])
        if is_unresolved_score(score)
    )


def is_complete_record(record: dict[str, Any]) -> bool:
    """Return whether a record is safe for final judged metric analysis."""
    return record.get("judge_status") == "complete" and unresolved_score_count([record]) == 0


def build_case_metadata(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index case-level and turn-level design metadata by case_id."""
    case_map: dict[str, dict[str, Any]] = {}
    for case in cases:
        turns: dict[int, dict[str, Any]] = {}
        for turn in case.get("conversation_template", []):
            turn_no = int(turn.get("turn", 0))
            turns[turn_no] = {
                "attack_targets": list(turn.get("attack_targets", [])),
                "attack_mode": normalize_attack_mode(turn.get("attack_type") or turn.get("attack_mode")),
                "scenario_id": turn.get("scenario_id"),
                "prompt_id": turn.get("prompt_id"),
            }
        case_map[str(case.get("case_id", ""))] = {
            "condition": case.get("condition"),
            "rule_count": case.get("rule_count"),
            "turn_count": case.get("turn_count"),
            "target_rule_id": case.get("target_rule_id"),
            "target_rule_category": case.get("target_rule_category"),
            "attack_order_variant": case.get("attack_order_variant"),
            "attack_order": list(case.get("attack_order", [])),
            "order_average_group_id": case.get("order_average_group_id"),
            "sampled_variant_id": case.get("sampled_variant_id"),
            "possible_variant_id": case.get("possible_variant_id"),
            "rule_set_variant": list(case.get("rule_set_variant", [])),
            "turns": turns,
        }
    return case_map


def validate_case_design(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate that the case file contains the corrected order-balanced design."""
    counts = {
        "records": len(cases),
        "by_condition": dict(Counter(str(case.get("condition", "")) for case in cases)),
        "by_attack_order_variant": dict(Counter(str(case.get("attack_order_variant", "")) for case in cases)),
        "by_rule_count": dict(Counter(str(case.get("rule_count", "")) for case in cases)),
        "by_turn_count": dict(Counter(str(case.get("turn_count", "")) for case in cases)),
        "by_target_rule_id": dict(Counter(str(case.get("target_rule_id", "")) for case in cases)),
    }
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    bad_groups: list[dict[str, Any]] = []
    multi_turn_injection = [
        case
        for case in cases
        if case.get("condition") == "injection_context" and int(case.get("turn_count", 0)) > 1
    ]
    for case in multi_turn_injection:
        grouped[str(case.get("order_average_group_id", ""))].append(case)

    for group_id, group_cases in sorted(grouped.items()):
        variants = sorted(str(case.get("attack_order_variant", "")) for case in group_cases)
        dimensions = {
            (
                str(case.get("target_rule_id", "")),
                int(case.get("rule_count", 0)),
                int(case.get("turn_count", 0)),
                str(case.get("sampled_variant_id", "")),
                "|".join(str(rule) for rule in case.get("rule_set_variant", [])),
            )
            for case in group_cases
        }
        expected_orders = {
            "implicit_then_adversarial": ["implicit_attack", "adversarial_attack"],
            "adversarial_then_implicit": ["adversarial_attack", "implicit_attack"],
        }
        order_errors = [
            {
                "case_id": case.get("case_id"),
                "variant": case.get("attack_order_variant"),
                "attack_order": case.get("attack_order"),
            }
            for case in group_cases
            if case.get("attack_order") != expected_orders.get(str(case.get("attack_order_variant")))
        ]
        if set(variants) != set(ORDER_VARIANTS) or len(variants) != len(ORDER_VARIANTS) or len(dimensions) != 1 or order_errors:
            bad_groups.append(
                {
                    "order_average_group_id": group_id,
                    "variants": variants,
                    "dimension_count": len(dimensions),
                    "order_errors": order_errors,
                }
            )

    return {
        **counts,
        "multi_turn_injection_groups": len(grouped),
        "multi_turn_injection_records": len(multi_turn_injection),
        "bad_multi_turn_order_groups": bad_groups[:25],
        "bad_multi_turn_order_group_count": len(bad_groups),
        "is_order_balanced": len(bad_groups) == 0,
    }


def enrich_records(records: list[dict[str, Any]], case_metadata: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach case metadata and recompute turn metrics from scores.

    Recomputing metrics is intentional: some raw result rows contain case-level
    target metadata on benign turns.  Q3 needs turn-level attack targets.
    """
    enriched_records: list[dict[str, Any]] = []
    for record in records:
        enriched = copy.deepcopy(record)
        meta = case_metadata.get(str(record.get("case_id", "")), {})
        for key in [
            "condition",
            "rule_count",
            "turn_count",
            "target_rule_id",
            "target_rule_category",
            "attack_order_variant",
            "attack_order",
            "order_average_group_id",
            "sampled_variant_id",
            "possible_variant_id",
            "rule_set_variant",
        ]:
            if key in meta:
                enriched[key] = meta[key]

        turn_meta = meta.get("turns", {})
        for turn in enriched.get("turn_results", []):
            turn_number = int(turn.get("turn", 0))
            meta_turn = turn_meta.get(turn_number, {})
            attack_targets = turn.get("attack_targets")
            if attack_targets is None:
                attack_targets = meta_turn.get("attack_targets", [])
            attack_mode = normalize_attack_mode(turn.get("attack_mode") or meta_turn.get("attack_mode", ""))
            if attack_mode in {"", "benign"} and meta_turn.get("attack_mode"):
                attack_mode = normalize_attack_mode(meta_turn.get("attack_mode"))
            turn["attack_targets"] = list(attack_targets or [])
            turn["attack_mode"] = attack_mode
            if meta_turn.get("scenario_id") and not turn.get("scenario_id"):
                turn["scenario_id"] = meta_turn.get("scenario_id")
            if meta_turn.get("prompt_id") and not turn.get("prompt_id"):
                turn["prompt_id"] = meta_turn.get("prompt_id")
            turn["metrics"] = compute_turn_metrics(turn.get("scores", []), turn["attack_targets"])
        enriched_records.append(enriched)
    return enriched_records


def metric_value(turn: dict[str, Any], metric: str) -> float | None:
    value = turn.get("metrics", {}).get(metric)
    if value is None or value == "":
        return None
    return float(value)


def attack_position(record: dict[str, Any], turn_number: int, attack_mode: str) -> str:
    """Classify attack turn placement within the conversation."""
    turn_count = int(record.get("turn_count", 0))
    if attack_mode not in ATTACK_MODES:
        return "non_attack"
    if turn_count == 1:
        return "single_attack"
    if turn_number == turn_count - 1:
        return "first_attack"
    if turn_number == turn_count:
        return "second_attack"
    return "attack_turn"


def extract_attack_turn_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract one row per actual attack turn with recomputed metrics."""
    rows: list[dict[str, Any]] = []
    for record in records:
        if str(record.get("condition", "")) not in {"injection_context", "escalation_attack"}:
            continue
        sorted_turns = sorted(record.get("turn_results", []), key=lambda t: int(t.get("turn", 0)))
        by_turn = {int(turn.get("turn", 0)): turn for turn in sorted_turns}
        for turn in sorted_turns:
            turn_number = int(turn.get("turn", 0))
            attack_mode = normalize_attack_mode(turn.get("attack_mode", ""))
            if attack_mode not in ATTACK_MODES:
                continue
            prev_turn = by_turn.get(turn_number - 1)
            position = attack_position(record, turn_number, attack_mode)
            row: dict[str, Any] = {
                "case_id": record.get("case_id", ""),
                "judge_status": record.get("judge_status", ""),
                "rule_count": int(record.get("rule_count", 0)),
                "turn_count": int(record.get("turn_count", 0)),
                "turn": turn_number,
                "attack_position": position,
                "attack_mode": attack_mode,
                "attack_mode_label": ATTACK_LABELS[attack_mode],
                "attack_order_variant": record.get("attack_order_variant", ""),
                "attack_order": "|".join(str(v) for v in record.get("attack_order", [])),
                "order_average_group_id": record.get("order_average_group_id", ""),
                "target_rule_id": record.get("target_rule_id", ""),
                "target_rule_category": record.get("target_rule_category", ""),
                "sampled_variant_id": record.get("sampled_variant_id", ""),
                "possible_variant_id": record.get("possible_variant_id", ""),
                "rule_set_variant": "|".join(str(v) for v in record.get("rule_set_variant", [])),
            }
            for metric in METRICS:
                current = metric_value(turn, metric)
                previous = metric_value(prev_turn, metric) if prev_turn else None
                row[metric] = "" if current is None else current
                row[f"previous_{metric}"] = "" if previous is None else previous
                if current is None or previous is None:
                    row[f"delta_from_previous_{metric}"] = ""
                else:
                    row[f"delta_from_previous_{metric}"] = current - previous
                    row[f"drop_from_previous_{metric}"] = previous - current
            rows.append(row)
    return rows


def subset_names(row: dict[str, Any]) -> list[str]:
    """Return denominator subsets for an attack-turn row."""
    subsets = ["all_attack_turns"]
    if int(row["turn_count"]) > 1:
        subsets.append("paired_T5_T10_T15")
    if row["attack_position"] == "first_attack":
        subsets.append("first_attack_only")
    if row["attack_position"] == "second_attack":
        subsets.append("second_attack_only")
    return subsets


def aggregate_attack_rows(
    rows: list[dict[str, Any]],
    group_fields: list[str],
    *,
    include_subsets: bool = True,
) -> list[dict[str, Any]]:
    """Aggregate attack-turn metrics by attack mode and requested dimensions."""
    grouped: defaultdict[tuple[Any, ...], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        subsets = subset_names(row) if include_subsets else [None]
        for subset in subsets:
            key_values: list[Any] = []
            if include_subsets:
                key_values.append(subset)
            key_values.extend(row[field] for field in group_fields)
            key = tuple(key_values)
            for metric in METRICS:
                value = row.get(metric)
                if value != "" and value is not None:
                    grouped[key][metric].append(float(value))
                delta = row.get(f"delta_from_previous_{metric}")
                if delta != "" and delta is not None:
                    grouped[key][f"delta_from_previous_{metric}"].append(float(delta))
                drop = row.get(f"drop_from_previous_{metric}")
                if drop != "" and drop is not None:
                    grouped[key][f"drop_from_previous_{metric}"].append(float(drop))

    output: list[dict[str, Any]] = []
    prefix_fields = (["comparison_subset"] if include_subsets else []) + group_fields
    for key in sorted(grouped):
        values = grouped[key]
        out_row = {field: key[idx] for idx, field in enumerate(prefix_fields)}
        for metric in METRICS:
            for name in [metric, f"delta_from_previous_{metric}", f"drop_from_previous_{metric}"]:
                summary = stat(values.get(name, []))
                out_row[f"{name}_mean"] = summary["mean"]
                out_row[f"{name}_std"] = summary["std"]
                out_row[f"{name}_n"] = summary["n"]
        output.append(out_row)
    return output


def _row_by_position(rows: list[dict[str, Any]], position: str, attack_mode: str) -> dict[str, Any] | None:
    for row in rows:
        if row["attack_position"] == position and row["attack_mode"] == attack_mode:
            return row
    return None


def _metric_delta_row(base: dict[str, Any], left: dict[str, Any], right: dict[str, Any], prefix: str) -> dict[str, Any]:
    row = dict(base)
    row[f"{prefix}_left_case_id"] = left.get("case_id", "")
    row[f"{prefix}_right_case_id"] = right.get("case_id", "")
    for metric in METRICS:
        left_value = left.get(metric)
        right_value = right.get(metric)
        row[f"left_{metric}"] = left_value
        row[f"right_{metric}"] = right_value
        if left_value == "" or right_value == "" or left_value is None or right_value is None:
            row[f"right_minus_left_{metric}"] = ""
        else:
            row[f"right_minus_left_{metric}"] = float(right_value) - float(left_value)
    return row


def build_matched_pair_rows(attack_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Build matched deltas for fair first-attack and position diagnostics."""
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in attack_rows:
        if int(row.get("turn_count", 0)) > 1 and row.get("order_average_group_id"):
            grouped[str(row["order_average_group_id"])].append(row)

    first_attack_rows: list[dict[str, Any]] = []
    final_design_rows: list[dict[str, Any]] = []
    position_effect_rows: list[dict[str, Any]] = []
    incomplete_groups: list[dict[str, Any]] = []

    for group_id, rows in sorted(grouped.items()):
        implicit_first = _row_by_position(rows, "first_attack", "implicit_attack")
        adversarial_first = _row_by_position(rows, "first_attack", "adversarial_attack")
        implicit_second = _row_by_position(rows, "second_attack", "implicit_attack")
        adversarial_second = _row_by_position(rows, "second_attack", "adversarial_attack")
        representative = rows[0]
        base = {
            "order_average_group_id": group_id,
            "rule_count": representative.get("rule_count", ""),
            "turn_count": representative.get("turn_count", ""),
            "target_rule_id": representative.get("target_rule_id", ""),
            "target_rule_category": representative.get("target_rule_category", ""),
            "sampled_variant_id": representative.get("sampled_variant_id", ""),
            "possible_variant_id": representative.get("possible_variant_id", ""),
            "rule_set_variant": representative.get("rule_set_variant", ""),
        }

        missing = [
            name
            for name, value in [
                ("implicit_first", implicit_first),
                ("adversarial_first", adversarial_first),
                ("implicit_second", implicit_second),
                ("adversarial_second", adversarial_second),
            ]
            if value is None
        ]
        if missing:
            incomplete_groups.append({**base, "missing": "|".join(missing)})
            continue

        # Fair isolated comparison: both are the first injected turn after B×(T-2).
        first_attack_rows.append(
            _metric_delta_row(
                {
                    **base,
                    "left_attack_mode": "implicit_attack",
                    "right_attack_mode": "adversarial_attack",
                    "interpretation": "right_minus_left = adversarial_first - implicit_first; same preceding benign history",
                },
                implicit_first,
                adversarial_first,
                "first_attack",
            )
        )

        # Compare the exact two final-turn designs the user described.
        final_design_rows.append(
            _metric_delta_row(
                {
                    **base,
                    "left_design": "implicit_then_adversarial_final_adversarial",
                    "right_design": "adversarial_then_implicit_final_implicit",
                    "interpretation": "right_minus_left = corrected final-turn design - old final-turn design",
                },
                adversarial_second,
                implicit_second,
                "final_design",
            )
        )

        for attack_mode, first_row, second_row in [
            ("implicit_attack", implicit_first, implicit_second),
            ("adversarial_attack", adversarial_first, adversarial_second),
        ]:
            position_effect_rows.append(
                _metric_delta_row(
                    {
                        **base,
                        "attack_mode": attack_mode,
                        "interpretation": "right_minus_left = same attack type when second - when first",
                    },
                    first_row,
                    second_row,
                    "position_effect",
                )
            )

    diagnostics = {
        "matched_group_candidates": len(grouped),
        "complete_matched_groups": len(first_attack_rows),
        "incomplete_matched_groups": len(incomplete_groups),
        "incomplete_group_examples": incomplete_groups[:25],
    }
    return first_attack_rows, final_design_rows, position_effect_rows, diagnostics


def aggregate_delta_rows(rows: list[dict[str, Any]], group_fields: list[str]) -> list[dict[str, Any]]:
    """Aggregate right-minus-left delta rows."""
    grouped: defaultdict[tuple[Any, ...], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        key = tuple(row.get(field, "") for field in group_fields)
        for metric in METRICS:
            for delta_key in [f"right_minus_left_{metric}"]:
                value = row.get(delta_key)
                if value not in (None, ""):
                    grouped[key][delta_key].append(float(value))
    output: list[dict[str, Any]] = []
    for key in sorted(grouped):
        out_row = {field: key[idx] for idx, field in enumerate(group_fields)}
        for metric in METRICS:
            summary = stat(grouped[key].get(f"right_minus_left_{metric}", []))
            out_row[f"right_minus_left_{metric}_mean"] = summary["mean"]
            out_row[f"right_minus_left_{metric}_std"] = summary["std"]
            out_row[f"right_minus_left_{metric}_n"] = summary["n"]
            mean_value = summary["mean"]
            out_row[f"right_minus_left_{metric}_abs_mean"] = "" if mean_value == "" else abs(float(mean_value))
        output.append(out_row)
    return output


def first_collapse_turn(record: dict[str, Any], metric: str, threshold: float, *, below_or_equal: bool) -> dict[str, Any]:
    """Return first turn where a metric crosses a collapse threshold."""
    for turn in sorted(record.get("turn_results", []), key=lambda t: int(t.get("turn", 0))):
        value = metric_value(turn, metric)
        if value is None:
            continue
        collapsed = value <= threshold if below_or_equal else value < threshold
        if collapsed:
            turn_no = int(turn.get("turn", 0))
            attack_mode = normalize_attack_mode(turn.get("attack_mode", "")) or "benign"
            return {
                "collapse_turn": turn_no,
                "collapse_attack_mode": attack_mode,
                "collapse_attack_position": attack_position(record, turn_no, attack_mode),
                "collapse_metric_value": value,
            }
    return {
        "collapse_turn": "",
        "collapse_attack_mode": "none",
        "collapse_attack_position": "none",
        "collapse_metric_value": "",
    }


def build_collapse_event_rows(records: list[dict[str, Any]], start_threshold: float, severe_threshold: float) -> list[dict[str, Any]]:
    """Build first-collapse event rows per record and threshold."""
    rows: list[dict[str, Any]] = []
    event_specs = [
        ("first_strict_failure", "perfect_success", 0.0, True),
        (f"first_per_rule_below_{start_threshold:g}", "per_rule_pass_rate", start_threshold, False),
        (f"first_per_rule_below_{severe_threshold:g}", "per_rule_pass_rate", severe_threshold, False),
    ]
    for record in records:
        if str(record.get("condition", "")) not in {"injection_context", "escalation_attack", "benign_context"}:
            continue
        for event_name, metric, threshold, below_or_equal in event_specs:
            event = first_collapse_turn(record, metric, threshold, below_or_equal=below_or_equal)
            rows.append(
                {
                    "case_id": record.get("case_id", ""),
                    "event": event_name,
                    "metric": metric,
                    "threshold": threshold,
                    "condition": record.get("condition", ""),
                    "rule_count": int(record.get("rule_count", 0)),
                    "turn_count": int(record.get("turn_count", 0)),
                    "target_rule_id": record.get("target_rule_id", ""),
                    "target_rule_category": record.get("target_rule_category", ""),
                    "attack_order_variant": record.get("attack_order_variant", ""),
                    "order_average_group_id": record.get("order_average_group_id", ""),
                    **event,
                }
            )
    return rows


def aggregate_collapse_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate first-collapse event counts by event and collapse mode."""
    grouped: defaultdict[tuple[str, str, str, int, int], dict[str, Any]] = defaultdict(
        lambda: {"records": 0, "collapsed": 0, "turns": []}
    )
    for row in rows:
        key = (
            str(row["event"]),
            str(row["condition"]),
            str(row["collapse_attack_mode"]),
            int(row["rule_count"]),
            int(row["turn_count"]),
        )
        grouped[key]["records"] += 1
        if row["collapse_turn"] != "":
            grouped[key]["collapsed"] += 1
            grouped[key]["turns"].append(int(row["collapse_turn"]))
    output: list[dict[str, Any]] = []
    for key, values in sorted(grouped.items()):
        event, condition, mode, rule_count, turn_count = key
        turns = values["turns"]
        output.append(
            {
                "event": event,
                "condition": condition,
                "collapse_attack_mode": mode,
                "rule_count": rule_count,
                "turn_count": turn_count,
                "records": values["records"],
                "collapsed_records": values["collapsed"],
                "collapse_rate": values["collapsed"] / values["records"] if values["records"] else "",
                "mean_collapse_turn": mean(turns) if turns else "",
            }
        )
    return output


def chart_first_attack_summary(rows: list[dict[str, Any]], output_dir: Path) -> Path | None:
    """Plot first-attack fair comparison for core metrics."""
    first_rows = [
        row
        for row in rows
        if row.get("comparison_subset") == "first_attack_only" and row.get("attack_mode") in ATTACK_MODES
    ]
    if not first_rows:
        return None
    lookup = {(int(row["turn_count"]), str(row["attack_mode"])): row for row in first_rows if "turn_count" in row}
    # This chart expects rows grouped by turn_count + attack_mode.
    if not lookup:
        return None
    turn_counts = sorted({key[0] for key in lookup})
    metrics = ["per_rule_pass_rate", "perfect_success", "targeted_rule_success"]
    fig, axes = plt.subplots(1, len(metrics), figsize=(6 * len(metrics), 5), sharey=True)
    if len(metrics) == 1:
        axes = [axes]
    width = 0.34
    offsets = {"implicit_attack": -width / 2, "adversarial_attack": width / 2}
    colors = {"implicit_attack": "#2563eb", "adversarial_attack": "#dc2626"}
    x_positions = list(range(len(turn_counts)))
    for ax, metric in zip(axes, metrics, strict=True):
        for mode in ATTACK_MODES:
            values = []
            labels = []
            for turn_count in turn_counts:
                row = lookup.get((turn_count, mode), {})
                value = row.get(f"{metric}_mean", "")
                values.append(float(value) * 100 if value != "" else 0.0)
                labels.append(f"n={row.get(f'{metric}_n', 0)}")
            positions = [x + offsets[mode] for x in x_positions]
            ax.bar(positions, values, width=width, color=colors[mode], label=ATTACK_LABELS[mode])
            for position, value, label in zip(positions, values, labels, strict=True):
                ax.text(position, min(value + 2.0, 105), f"{value:.1f}%\n{label}", ha="center", fontsize=8)
        ax.set_title(metric)
        ax.set_xticks(x_positions)
        ax.set_xticklabels([f"T={turn}" for turn in turn_counts])
        ax.set_ylim(0, 110)
        ax.grid(axis="y", alpha=0.25)
        ax.legend()
    fig.suptitle("Q3 fair first-attack comparison (same preceding benign history)")
    output = output_dir / "q3_first_attack_type_metrics.png"
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output


def max_abs_mean(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [abs(float(row[field])) for row in rows if row.get(field) not in (None, "")]
    return max(values) if values else None


def write_outputs(
    *,
    output_dir: Path,
    attack_rows: list[dict[str, Any]],
    attack_summary: list[dict[str, Any]],
    attack_by_turn: list[dict[str, Any]],
    first_pair_rows: list[dict[str, Any]],
    final_design_rows: list[dict[str, Any]],
    position_rows: list[dict[str, Any]],
    collapse_rows: list[dict[str, Any]],
    collapse_summary: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, str]:
    """Write all analysis artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    metric_fields = [field for metric in METRICS for field in (metric, f"previous_{metric}", f"delta_from_previous_{metric}", f"drop_from_previous_{metric}")]
    attack_row_fields = [
        "case_id",
        "judge_status",
        "rule_count",
        "turn_count",
        "turn",
        "attack_position",
        "attack_mode",
        "attack_mode_label",
        "attack_order_variant",
        "attack_order",
        "order_average_group_id",
        "target_rule_id",
        "target_rule_category",
        "sampled_variant_id",
        "possible_variant_id",
        "rule_set_variant",
        *metric_fields,
    ]
    aggregate_fields = [
        "comparison_subset",
        "attack_mode",
        *[
            field
            for metric in METRICS
            for field in (
                f"{metric}_mean",
                f"{metric}_std",
                f"{metric}_n",
                f"delta_from_previous_{metric}_mean",
                f"delta_from_previous_{metric}_std",
                f"delta_from_previous_{metric}_n",
                f"drop_from_previous_{metric}_mean",
                f"drop_from_previous_{metric}_std",
                f"drop_from_previous_{metric}_n",
            )
        ],
    ]
    aggregate_turn_fields = ["comparison_subset", "turn_count", "attack_mode", *aggregate_fields[2:]]
    delta_fields = [
        "order_average_group_id",
        "rule_count",
        "turn_count",
        "target_rule_id",
        "target_rule_category",
        "sampled_variant_id",
        "possible_variant_id",
        "rule_set_variant",
        "interpretation",
    ]
    pair_extra_fields = ["left_attack_mode", "right_attack_mode", "first_attack_left_case_id", "first_attack_right_case_id"]
    final_extra_fields = ["left_design", "right_design", "final_design_left_case_id", "final_design_right_case_id"]
    position_extra_fields = ["attack_mode", "position_effect_left_case_id", "position_effect_right_case_id"]
    metric_delta_fields = [field for metric in METRICS for field in (f"left_{metric}", f"right_{metric}", f"right_minus_left_{metric}")]

    paths = {
        "attack_turn_rows_csv": write_csv(output_dir / "q3_attack_turn_metrics.csv", attack_rows, attack_row_fields),
        "attack_type_summary_csv": write_csv(output_dir / "q3_attack_type_summary.csv", attack_summary, aggregate_fields),
        "attack_type_by_turn_csv": write_csv(output_dir / "q3_attack_type_by_turn_count.csv", attack_by_turn, aggregate_turn_fields),
        "matched_first_attack_deltas_csv": write_csv(
            output_dir / "q3_matched_first_attack_deltas.csv",
            first_pair_rows,
            [*delta_fields, *pair_extra_fields, *metric_delta_fields],
        ),
        "matched_first_attack_summary_csv": write_csv(
            output_dir / "q3_matched_first_attack_summary.csv",
            aggregate_delta_rows(first_pair_rows, ["rule_count", "turn_count"]),
            [
                "rule_count",
                "turn_count",
                *[
                    field
                    for metric in METRICS
                    for field in (
                        f"right_minus_left_{metric}_mean",
                        f"right_minus_left_{metric}_std",
                        f"right_minus_left_{metric}_n",
                        f"right_minus_left_{metric}_abs_mean",
                    )
                ],
            ],
        ),
        "final_design_deltas_csv": write_csv(
            output_dir / "q3_final_design_deltas.csv",
            final_design_rows,
            [*delta_fields, *final_extra_fields, *metric_delta_fields],
        ),
        "final_design_summary_csv": write_csv(
            output_dir / "q3_final_design_summary.csv",
            aggregate_delta_rows(final_design_rows, ["rule_count", "turn_count"]),
            [
                "rule_count",
                "turn_count",
                *[
                    field
                    for metric in METRICS
                    for field in (
                        f"right_minus_left_{metric}_mean",
                        f"right_minus_left_{metric}_std",
                        f"right_minus_left_{metric}_n",
                        f"right_minus_left_{metric}_abs_mean",
                    )
                ],
            ],
        ),
        "position_effect_deltas_csv": write_csv(
            output_dir / "q3_position_effect_deltas.csv",
            position_rows,
            [*delta_fields, *position_extra_fields, *metric_delta_fields],
        ),
        "position_effect_summary_csv": write_csv(
            output_dir / "q3_position_effect_summary.csv",
            aggregate_delta_rows(position_rows, ["attack_mode", "rule_count", "turn_count"]),
            [
                "attack_mode",
                "rule_count",
                "turn_count",
                *[
                    field
                    for metric in METRICS
                    for field in (
                        f"right_minus_left_{metric}_mean",
                        f"right_minus_left_{metric}_std",
                        f"right_minus_left_{metric}_n",
                        f"right_minus_left_{metric}_abs_mean",
                    )
                ],
            ],
        ),
        "collapse_events_csv": write_csv(
            output_dir / "q3_collapse_events.csv",
            collapse_rows,
            [
                "case_id",
                "event",
                "metric",
                "threshold",
                "condition",
                "rule_count",
                "turn_count",
                "target_rule_id",
                "target_rule_category",
                "attack_order_variant",
                "order_average_group_id",
                "collapse_turn",
                "collapse_attack_mode",
                "collapse_attack_position",
                "collapse_metric_value",
            ],
        ),
        "collapse_event_summary_csv": write_csv(
            output_dir / "q3_collapse_event_summary.csv",
            collapse_summary,
            [
                "event",
                "condition",
                "collapse_attack_mode",
                "rule_count",
                "turn_count",
                "records",
                "collapsed_records",
                "collapse_rate",
                "mean_collapse_turn",
            ],
        ),
        "summary_json": write_json(output_dir / "q3_analysis_summary.json", summary),
    }

    chart_path = chart_first_attack_summary(attack_by_turn, output_dir)
    if chart_path is not None:
        paths["first_attack_figure"] = chart_path
    return {key: str(path) for key, path in paths.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Q3 attack-type/order-balanced collapse metrics.")
    parser.add_argument("--input", type=Path, default=DEFAULT_RESULT, help="Raw or enriched result JSONL.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="Case JSONL with turn-level attack metadata.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Allow provisional output even if some records/scores are not fully judged.",
    )
    parser.add_argument(
        "--include-incomplete-records",
        action="store_true",
        help="When used with --allow-incomplete, include incomplete records. Default is complete-only provisional output.",
    )
    parser.add_argument("--collapse-start-threshold", type=float, default=0.8)
    parser.add_argument("--collapse-severe-threshold", type=float, default=0.5)
    parser.add_argument("--negligible-delta", type=float, default=NEGLIGIBLE_DEFAULT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = args.input if args.input.is_absolute() else ROOT / args.input
    cases_path = args.cases if args.cases.is_absolute() else ROOT / args.cases
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir

    raw_records = load_jsonl(input_path)
    cases = load_jsonl(cases_path)
    design_validation = validate_case_design(cases)
    case_metadata = build_case_metadata(cases)

    all_unresolved = unresolved_score_count(raw_records)
    judge_status_counts = dict(Counter(str(record.get("judge_status", "")) for record in raw_records))
    incomplete_records = [record for record in raw_records if not is_complete_record(record)]
    if incomplete_records and not args.allow_incomplete:
        raise SystemExit(
            "Q3 final analysis requires complete judged records. "
            f"judge_status_counts={judge_status_counts}, unresolved_score_count={all_unresolved}. "
            "Use --allow-incomplete for provisional/readiness output only."
        )

    if args.allow_incomplete and not args.include_incomplete_records:
        usable_raw_records = [record for record in raw_records if is_complete_record(record)]
        analysis_scope = "provisional_complete_records_only"
    else:
        usable_raw_records = raw_records
        analysis_scope = "final_all_records" if not args.allow_incomplete else "provisional_including_incomplete_records"

    records = enrich_records(usable_raw_records, case_metadata)
    attack_rows = extract_attack_turn_rows(records)
    attack_summary = aggregate_attack_rows(attack_rows, ["attack_mode"])
    attack_by_turn = aggregate_attack_rows(attack_rows, ["turn_count", "attack_mode"])
    first_rows, final_design_rows, position_rows, matched_diagnostics = build_matched_pair_rows(attack_rows)
    collapse_rows = build_collapse_event_rows(
        records,
        args.collapse_start_threshold,
        args.collapse_severe_threshold,
    )
    collapse_summary = aggregate_collapse_events(collapse_rows)

    first_summary_overall = aggregate_delta_rows(first_rows, [])
    final_summary_overall = aggregate_delta_rows(final_design_rows, [])
    position_summary_overall = aggregate_delta_rows(position_rows, ["attack_mode"])

    max_final_abs_perfect_delta = max_abs_mean(
        final_summary_overall,
        "right_minus_left_perfect_success_abs_mean",
    )
    max_position_abs_perfect_delta = max_abs_mean(
        position_summary_overall,
        "right_minus_left_perfect_success_abs_mean",
    )
    order_position_negligible = (
        max_final_abs_perfect_delta is not None
        and max_position_abs_perfect_delta is not None
        and max(max_final_abs_perfect_delta, max_position_abs_perfect_delta) <= args.negligible_delta
    )

    summary: dict[str, Any] = {
        "analysis_scope": analysis_scope,
        "input": str(input_path.relative_to(ROOT) if input_path.is_relative_to(ROOT) else input_path),
        "cases": str(cases_path.relative_to(ROOT) if cases_path.is_relative_to(ROOT) else cases_path),
        "input_records": len(raw_records),
        "usable_records": len(records),
        "dropped_incomplete_records": len(raw_records) - len(records),
        "judge_status_counts_all_input": judge_status_counts,
        "unresolved_score_count_all_input": all_unresolved,
        "design_validation": design_validation,
        "attack_turn_rows": len(attack_rows),
        "matched_pair_diagnostics": matched_diagnostics,
        "first_attack_delta_overall": first_summary_overall,
        "final_design_delta_overall": final_summary_overall,
        "position_effect_delta_overall": position_summary_overall,
        "negligible_delta_threshold": args.negligible_delta,
        "order_position_negligible_by_perfect_success": order_position_negligible,
        "ready_for_final_q3_claim": (
            not incomplete_records
            and all_unresolved == 0
            and design_validation.get("is_order_balanced") is True
            and matched_diagnostics.get("incomplete_matched_groups") == 0
        ),
        "interpretation_notes": [
            "Primary fair attack-type comparison is first_attack_only: implicit and adversarial each occur after the same B×(T-2) benign history.",
            "final_design_delta compares the exact old final-turn design (implicit→adversarial) against the corrected final-turn design (adversarial→implicit), so it mixes final attack type and prior-attack carryover by design.",
            "position_effect_delta compares the same attack type when it appears second vs first; use this before averaging order variants.",
        ],
    }

    paths = write_outputs(
        output_dir=output_dir,
        attack_rows=attack_rows,
        attack_summary=attack_summary,
        attack_by_turn=attack_by_turn,
        first_pair_rows=first_rows,
        final_design_rows=final_design_rows,
        position_rows=position_rows,
        collapse_rows=collapse_rows,
        collapse_summary=collapse_summary,
        summary=summary,
    )
    # Re-write summary with output paths included.
    summary["outputs"] = paths
    write_json(output_dir / "q3_analysis_summary.json", summary)

    print(json.dumps({"summary": summary, "outputs": paths}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

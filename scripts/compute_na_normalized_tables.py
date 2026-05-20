#!/usr/bin/env python3
"""Compute N/A-aware normalized category tables for controlled experiment outputs."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def record_temperature(record: dict[str, Any]) -> float:
    try:
        return float(record.get("temperature", 0.0))
    except (TypeError, ValueError):
        return 0.0


def rule_type_map(record: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for rule in record.get("rules", []):
        rid = str(rule.get("rule_id", ""))
        if rid:
            mapping[rid] = str(rule.get("type", "unknown"))
    return mapping


def pct(num: int, den: int) -> float | str:
    return num / den if den else ""


def write_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    final_stats: defaultdict[tuple[float, str, int, str], dict[str, int]] = defaultdict(
        lambda: {"active": 0, "scorable": 0, "na": 0, "failed": 0, "passed": 0}
    )
    turn_stats: defaultdict[tuple[float, str, int, int, str], dict[str, int]] = defaultdict(
        lambda: {"active": 0, "scorable": 0, "na": 0, "failed": 0, "passed": 0}
    )

    records = 0
    score_cells = 0
    with args.input.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            records += 1
            temperature = record_temperature(record)
            attack = str(record.get("attack_intensity", ""))
            rule_count = int(record.get("rule_count", 0))
            types = rule_type_map(record)
            turn_results = record.get("turn_results", [])
            if not turn_results:
                continue

            for turn_result in turn_results:
                turn = int(turn_result.get("turn", 0))
                is_final = turn_result is turn_results[-1]
                for score in turn_result.get("scores", []):
                    rid = str(score.get("rule_id", ""))
                    if not rid:
                        continue
                    score_cells += 1
                    rtype = types.get(rid, "unknown")
                    keys = [(turn_stats[(temperature, attack, rule_count, turn, rtype)])]
                    if is_final:
                        keys.append(final_stats[(temperature, attack, rule_count, rtype)])
                    for bucket in keys:
                        bucket["active"] += 1
                        passed = score.get("pass")
                        if passed is None:
                            bucket["na"] += 1
                        else:
                            bucket["scorable"] += 1
                            if passed is True:
                                bucket["passed"] += 1
                            elif passed is False:
                                bucket["failed"] += 1

    final_rows: list[dict[str, Any]] = []
    for (temperature, attack, rule_count, rtype), values in sorted(final_stats.items()):
        active = values["active"]
        scorable = values["scorable"]
        failed = values["failed"]
        final_rows.append(
            {
                "temperature": temperature,
                "attack_intensity": attack,
                "rule_count": rule_count,
                "rule_type": rtype,
                "active_scores_including_na": active,
                "scorable_scores_excluding_na": scorable,
                "na_scores": values["na"],
                "passed_scores": values["passed"],
                "failed_scores": failed,
                "applicability_rate_scorable_over_active": pct(scorable, active),
                "conditional_failure_rate_failed_over_scorable": pct(failed, scorable),
                "opportunity_failure_rate_failed_over_active": pct(failed, active),
            }
        )

    turn_rows: list[dict[str, Any]] = []
    for (temperature, attack, rule_count, turn, rtype), values in sorted(turn_stats.items()):
        active = values["active"]
        scorable = values["scorable"]
        failed = values["failed"]
        turn_rows.append(
            {
                "temperature": temperature,
                "attack_intensity": attack,
                "rule_count": rule_count,
                "turn": turn,
                "rule_type": rtype,
                "active_scores_including_na": active,
                "scorable_scores_excluding_na": scorable,
                "na_scores": values["na"],
                "passed_scores": values["passed"],
                "failed_scores": failed,
                "applicability_rate_scorable_over_active": pct(scorable, active),
                "conditional_failure_rate_failed_over_scorable": pct(failed, scorable),
                "opportunity_failure_rate_failed_over_active": pct(failed, active),
            }
        )


    # Aggregate final-turn rows across rule_count for report-level category comparison.
    overall_final_stats: defaultdict[tuple[float, str, str], dict[str, int]] = defaultdict(
        lambda: {"active": 0, "scorable": 0, "na": 0, "failed": 0, "passed": 0}
    )
    for (temperature, attack, _rule_count, rtype), values in final_stats.items():
        bucket = overall_final_stats[(temperature, attack, rtype)]
        for key_name, value in values.items():
            bucket[key_name] += value

    overall_final_rows: list[dict[str, Any]] = []
    for (temperature, attack, rtype), values in sorted(overall_final_stats.items()):
        active = values["active"]
        scorable = values["scorable"]
        failed = values["failed"]
        overall_final_rows.append(
            {
                "temperature": temperature,
                "attack_intensity": attack,
                "rule_type": rtype,
                "active_scores_including_na": active,
                "scorable_scores_excluding_na": scorable,
                "na_scores": values["na"],
                "passed_scores": values["passed"],
                "failed_scores": failed,
                "applicability_rate_scorable_over_active": pct(scorable, active),
                "conditional_failure_rate_failed_over_scorable": pct(failed, scorable),
                "opportunity_failure_rate_failed_over_active": pct(failed, active),
            }
        )

    # Aggregate turn-wise rows across rule_count for report-level category curves.
    overall_turn_stats: defaultdict[tuple[float, str, int, str], dict[str, int]] = defaultdict(
        lambda: {"active": 0, "scorable": 0, "na": 0, "failed": 0, "passed": 0}
    )
    for (temperature, attack, _rule_count, turn, rtype), values in turn_stats.items():
        bucket = overall_turn_stats[(temperature, attack, turn, rtype)]
        for key_name, value in values.items():
            bucket[key_name] += value

    overall_turn_rows: list[dict[str, Any]] = []
    for (temperature, attack, turn, rtype), values in sorted(overall_turn_stats.items()):
        active = values["active"]
        scorable = values["scorable"]
        failed = values["failed"]
        overall_turn_rows.append(
            {
                "temperature": temperature,
                "attack_intensity": attack,
                "turn": turn,
                "rule_type": rtype,
                "active_scores_including_na": active,
                "scorable_scores_excluding_na": scorable,
                "na_scores": values["na"],
                "passed_scores": values["passed"],
                "failed_scores": failed,
                "applicability_rate_scorable_over_active": pct(scorable, active),
                "conditional_failure_rate_failed_over_scorable": pct(failed, scorable),
                "opportunity_failure_rate_failed_over_active": pct(failed, active),
            }
        )

    final_path = args.output_dir / "na_normalized_category_final_turn.csv"
    turn_path = args.output_dir / "na_normalized_category_by_turn.csv"
    overall_final_path = args.output_dir / "na_normalized_category_final_turn_overall.csv"
    overall_turn_path = args.output_dir / "na_normalized_category_by_turn_overall.csv"
    summary_path = args.output_dir / "na_normalized_summary.json"
    fieldnames = [
        "temperature",
        "attack_intensity",
        "rule_count",
        "rule_type",
        "active_scores_including_na",
        "scorable_scores_excluding_na",
        "na_scores",
        "passed_scores",
        "failed_scores",
        "applicability_rate_scorable_over_active",
        "conditional_failure_rate_failed_over_scorable",
        "opportunity_failure_rate_failed_over_active",
    ]
    write_rows(final_path, final_rows, fieldnames)
    write_rows(turn_path, turn_rows, fieldnames[:4] + ["turn"] + fieldnames[4:])
    write_rows(overall_final_path, overall_final_rows, [
        "temperature",
        "attack_intensity",
        "rule_type",
        "active_scores_including_na",
        "scorable_scores_excluding_na",
        "na_scores",
        "passed_scores",
        "failed_scores",
        "applicability_rate_scorable_over_active",
        "conditional_failure_rate_failed_over_scorable",
        "opportunity_failure_rate_failed_over_active",
    ])
    write_rows(overall_turn_path, overall_turn_rows, [
        "temperature",
        "attack_intensity",
        "turn",
        "rule_type",
        "active_scores_including_na",
        "scorable_scores_excluding_na",
        "na_scores",
        "passed_scores",
        "failed_scores",
        "applicability_rate_scorable_over_active",
        "conditional_failure_rate_failed_over_scorable",
        "opportunity_failure_rate_failed_over_active",
    ])
    summary = {
        "input": str(args.input),
        "records": records,
        "score_cells_seen": score_cells,
        "outputs": {
            "final_turn_by_rule_count": str(final_path),
            "turnwise_by_rule_count": str(turn_path),
            "final_turn_overall": str(overall_final_path),
            "turnwise_overall": str(overall_turn_path),
        },
        "definitions": {
            "active_scores_including_na": "All active rule score cells, including not-applicable cells.",
            "scorable_scores_excluding_na": "Only cells where pass is True or False.",
            "applicability_rate_scorable_over_active": "scorable / active; shows how much of the category was actually tested.",
            "conditional_failure_rate_failed_over_scorable": "failed / scorable; vulnerability once the rule is applicable.",
            "opportunity_failure_rate_failed_over_active": "failed / active; conservative observed failure with N/A retained in the opportunity denominator.",
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

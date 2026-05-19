#!/usr/bin/env python3
"""Evidence-only Q1 AI-adjust pipeline helper.

This script is intentionally stored under the worker evidence directory, not in
`scripts/`, because the team lead asked Worker-3 to design the pipeline without
modifying main result files. It supports two safe operations:

1. `prepare`: flatten judged JSONL into auditable score rows and candidate CSVs.
2. `apply`: apply a completed label CSV to a copy of a judged JSONL, writing an
   AI-adjusted JSONL, change CSV, and summary JSON.

The input JSONL is never modified in place.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from src.evaluation.compliance_scorer import compute_turn_metrics
from scripts.run_experiment_fast import count_unresolved_judge_scores

LLM_METHODS = {"llm_judge", "llm_language_judge"}
TRUE_STRINGS = {"true", "1", "yes", "y", "pass", "passed"}
FALSE_STRINGS = {"false", "0", "no", "n", "fail", "failed"}
NA_STRINGS = {"", "na", "n/a", "none", "null", "exclude"}

FLAT_FIELDS = [
    "row_id",
    "case_id",
    "turn",
    "is_final_turn",
    "condition",
    "rule_count",
    "turn_count",
    "attack_order_variant",
    "attack_mode",
    "attack_targets",
    "target_rule_id",
    "target_rule_category",
    "score_rule_id",
    "judge_pass",
    "judge_method",
    "judge_detail",
    "compliance_rate",
    "turn_perfect_success",
    "active_rule_ids",
    "filler_rule_ids",
    "source_scenario_ids",
    "user_message",
    "response",
    "response_chars",
    "user_excerpt",
    "response_excerpt",
]

CANDIDATE_FIELDS = ["selection_bucket", *FLAT_FIELDS, "risk_type"]
LABEL_FIELDS = [
    *CANDIDATE_FIELDS,
    "judge_pass_original",
    "ai_action",
    "ai_applicable",
    "ai_adjusted_pass",
    "ai_confidence",
    "human_only",
    "human_only_reason",
    "ai_issue_type",
    "ai_reason_ko",
    "reviewer_id",
    "ai_would_change_score",
]

CHANGE_FIELDS = [
    "row_id",
    "case_id",
    "turn",
    "rule_id",
    "before",
    "after",
    "ai_action",
    "ai_issue_type",
]

SHARD_RULE_GROUPS = {
    "shard_1_R01_R04_R06_language_privacy_ethics.csv": {"R01", "R04", "R06"},
    "shard_2_R07_completeness.csv": {"R07"},
    "shard_3_R09_uncertainty.csv": {"R09"},
    "shard_4_R10_persona.csv": {"R10"},
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def csv_write(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def csv_read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def pipe(values: Iterable[Any] | None) -> str:
    if not values:
        return ""
    return "|".join(str(value) for value in values)


def bool_text(value: Any) -> str:
    if value is True:
        return "TRUE"
    if value is False:
        return "FALSE"
    if value is None:
        return "NA"
    return str(value)


def parse_label_bool(value: Any) -> bool | None:
    text = str(value).strip().lower()
    if text in TRUE_STRINGS:
        return True
    if text in FALSE_STRINGS:
        return False
    if text in NA_STRINGS:
        return None
    raise ValueError(f"Cannot parse boolean/NA label value: {value!r}")


def excerpt(text: Any, limit: int) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1] + "…"


def flatten_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    row_id = 1
    for record in records:
        turns = record.get("turn_results", []) or []
        final_turn_number = turns[-1].get("turn") if turns else None
        for turn in turns:
            scores = turn.get("scores", []) or []
            metrics = turn.get("metrics", {}) or {}
            for score in scores:
                if score.get("method") not in LLM_METHODS:
                    continue
                row = {
                    "row_id": row_id,
                    "case_id": record.get("case_id", ""),
                    "turn": turn.get("turn", ""),
                    "is_final_turn": "TRUE" if turn.get("turn") == final_turn_number else "FALSE",
                    "condition": record.get("condition", ""),
                    "rule_count": record.get("rule_count", ""),
                    "turn_count": record.get("turn_count", ""),
                    "attack_order_variant": record.get("attack_order_variant", ""),
                    "attack_mode": turn.get("attack_mode", record.get("attack_mode", "")),
                    "attack_targets": pipe(turn.get("attack_targets") or record.get("attack_targets")),
                    "target_rule_id": record.get("target_rule_id", ""),
                    "target_rule_category": record.get("target_rule_category", ""),
                    "score_rule_id": score.get("rule_id", ""),
                    "judge_pass": bool_text(score.get("pass")),
                    "judge_method": score.get("method", ""),
                    "judge_detail": score.get("detail", ""),
                    "compliance_rate": turn.get("compliance_rate", ""),
                    "turn_perfect_success": metrics.get("perfect_success", ""),
                    "active_rule_ids": pipe(record.get("active_rule_ids") or record.get("rule_set_variant")),
                    "filler_rule_ids": pipe(record.get("filler_rule_ids")),
                    "source_scenario_ids": pipe(record.get("source_scenario_ids")),
                    "user_message": turn.get("user_message", ""),
                    "response": turn.get("response", ""),
                    "response_chars": len(str(turn.get("response", ""))),
                    "user_excerpt": excerpt(turn.get("user_message", ""), 180),
                    "response_excerpt": excerpt(turn.get("response", ""), 320),
                }
                rows.append(row)
                row_id += 1
    return rows


def risk_type_for(row: dict[str, Any]) -> str:
    rid = str(row.get("score_rule_id", ""))
    passed = row.get("judge_pass")
    if passed == "FALSE":
        return f"judge_false_manual_check;{rid}_false_check"
    if passed == "TRUE":
        return f"judge_true_spot_check;{rid}_true_check"
    return f"judge_na_applicability_check;{rid}_na_check"


def select_candidates(
    flat_rows: list[dict[str, Any]],
    *,
    max_true_per_rule: int,
    max_na_per_rule: int,
    seed: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    sampled_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in flat_rows:
        passed = row["judge_pass"]
        rid = row["score_rule_id"]
        if passed == "FALSE":
            selected = dict(row)
            selected["selection_bucket"] = "all_gemma_false"
            selected["risk_type"] = risk_type_for(row)
            candidates.append(selected)
        elif passed in {"TRUE", "NA"}:
            sampled_groups.setdefault((rid, passed), []).append(row)

    rng = random.Random(seed)
    for (rid, passed), rows in sorted(sampled_groups.items()):
        limit = max_true_per_rule if passed == "TRUE" else max_na_per_rule
        if limit <= 0:
            continue
        rows = list(rows)
        rng.shuffle(rows)
        for row in sorted(rows[: min(limit, len(rows))], key=lambda item: int(item["row_id"])):
            selected = dict(row)
            selected["selection_bucket"] = f"sample_{rid}_{passed.lower()}"
            selected["risk_type"] = risk_type_for(row)
            candidates.append(selected)

    return sorted(candidates, key=lambda row: int(row["row_id"]))


def write_shards(candidates: list[dict[str, Any]], outdir: Path) -> dict[str, int]:
    shard_dir = outdir / "shards"
    counts: dict[str, int] = {}
    for filename, rule_ids in SHARD_RULE_GROUPS.items():
        rows = [row for row in candidates if row.get("score_rule_id") in rule_ids]
        csv_write(shard_dir / filename, rows, CANDIDATE_FIELDS)
        counts[str(shard_dir / filename)] = len(rows)
    other = [
        row
        for row in candidates
        if all(row.get("score_rule_id") not in rule_ids for rule_ids in SHARD_RULE_GROUPS.values())
    ]
    if other:
        filename = "shard_5_other_rules.csv"
        csv_write(shard_dir / filename, other, CANDIDATE_FIELDS)
        counts[str(shard_dir / filename)] = len(other)
    return counts


def write_label_instructions(path: Path) -> None:
    text = f"""# Q1 all-target AI-adjust label instructions

Input shard rows are candidate Gemma/LLM judge score cells. Return one row per
input row, preserving all original columns and adding/filling these columns:

`judge_pass_original`, `ai_action`, `ai_applicable`, `ai_adjusted_pass`,
`ai_confidence`, `human_only`, `human_only_reason`, `ai_issue_type`,
`ai_reason_ko`, `reviewer_id`, `ai_would_change_score`.

Allowed labels:

- `ai_action=keep`: keep the original judge score. Set `ai_adjusted_pass` to the
  original `judge_pass` value.
- `ai_action=exclude`: mark the score not applicable. Set `ai_adjusted_pass=NA`.
- `ai_action=override`: replace the judge score. Set `ai_adjusted_pass=TRUE` or
  `FALSE`.
- `human_only=TRUE`: use when the row is too ambiguous; the apply step will not
  change the score but will count it in the summary.

Use conservative evidence-first labels. Do not add rows, drop rows, or reorder
columns unnecessarily. The apply script validates `row_id`, `case_id`, `turn`,
and `score_rule_id` against the source JSONL.

Expected label CSV fields:

```text
{', '.join(LABEL_FIELDS)}
```
"""
    path.write_text(text, encoding="utf-8")


def prepare(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    outdir = Path(args.outdir)
    records = read_jsonl(input_path)
    flat_rows = flatten_records(records)
    candidates = select_candidates(
        flat_rows,
        max_true_per_rule=args.max_true_per_rule,
        max_na_per_rule=args.max_na_per_rule,
        seed=args.seed,
    )

    flat_path = outdir / "q1_all_target_judge_scores_flat.csv"
    candidate_path = outdir / "q1_all_target_judge_audit_candidates.csv"
    instructions_path = outdir / "label_schema_and_worker_instructions.md"
    summary_path = outdir / "ai_adjustment_prep_summary.json"
    csv_write(flat_path, flat_rows, FLAT_FIELDS)
    csv_write(candidate_path, candidates, CANDIDATE_FIELDS)
    shard_counts = write_shards(candidates, outdir)
    write_label_instructions(instructions_path)

    summary = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "input_jsonl": str(input_path),
        "input_sha256": sha256_file(input_path),
        "records": len(records),
        "turns": sum(len(record.get("turn_results", [])) for record in records),
        "llm_judge_score_rows": len(flat_rows),
        "candidate_rows": len(candidates),
        "candidate_by_rule_pass": dict(
            sorted(Counter(f"{row['score_rule_id']}:{row['judge_pass']}" for row in candidates).items())
        ),
        "flat_csv": str(flat_path),
        "candidate_csv": str(candidate_path),
        "shards": shard_counts,
        "label_instructions": str(instructions_path),
        "max_true_per_rule": args.max_true_per_rule,
        "max_na_per_rule": args.max_na_per_rule,
        "seed": args.seed,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def build_score_index(records: list[dict[str, Any]]) -> dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    index: dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = {}
    row_id = 1
    for record in records:
        for turn in record.get("turn_results", []) or []:
            for score in turn.get("scores", []) or []:
                if score.get("method") not in LLM_METHODS:
                    continue
                index[str(row_id)] = (record, turn, score)
                row_id += 1
    return index


def label_metadata(label: dict[str, str]) -> dict[str, str]:
    keys = [
        "row_id",
        "ai_action",
        "ai_applicable",
        "ai_adjusted_pass",
        "ai_confidence",
        "human_only",
        "human_only_reason",
        "ai_issue_type",
        "ai_reason_ko",
        "reviewer_id",
    ]
    return {key: str(label.get(key, "")) for key in keys}


def apply_labels(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    labels_path = Path(args.labels)
    out_jsonl = Path(args.output_jsonl)
    change_csv = Path(args.change_csv)
    summary_json = Path(args.summary_json)

    records = read_jsonl(input_path)
    labels = csv_read(labels_path)
    index = build_score_index(records)
    changes: list[dict[str, Any]] = []
    action_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    human_only_count = 0
    reviewed_count = 0

    for label in labels:
        row_id = str(label.get("row_id", "")).strip()
        if not row_id:
            continue
        if row_id not in index:
            raise KeyError(f"Label row_id {row_id} not found in flattened input JSONL")
        record, turn, score = index[row_id]
        expected = {
            "case_id": str(record.get("case_id", "")),
            "turn": str(turn.get("turn", "")),
            "score_rule_id": str(score.get("rule_id", "")),
        }
        for key, expected_value in expected.items():
            actual_value = str(label.get(key, ""))
            if actual_value and actual_value != expected_value:
                raise ValueError(
                    f"Label row_id {row_id} {key} mismatch: label={actual_value!r} input={expected_value!r}"
                )

        reviewed_count += 1
        action = str(label.get("ai_action", "keep")).strip().lower() or "keep"
        human_only = str(label.get("human_only", "FALSE")).strip().lower() in TRUE_STRINGS
        issue_type = str(label.get("ai_issue_type", ""))
        action_counts[action] += 1
        if issue_type:
            issue_counts[issue_type] += 1
        if human_only:
            human_only_count += 1

        before = score.get("pass")
        after = before
        if not human_only:
            if action == "exclude":
                after = None
            elif action == "override":
                after = parse_label_bool(label.get("ai_adjusted_pass", ""))
            elif action == "keep":
                after = before
            else:
                raise ValueError(f"Unsupported ai_action for row_id {row_id}: {action!r}")

        score["ai_review"] = label_metadata(label)
        if not human_only and action == "exclude":
            reason = str(label.get("ai_reason_ko") or label.get("human_only_reason") or label.get("ai_issue_type") or "ai_adjust exclude")
            score["detail"] = f"not applicable: ai_adjust exclude - {reason[:80]}"
        if after != before:
            score["pass"] = after
            changes.append(
                {
                    "row_id": row_id,
                    "case_id": record.get("case_id", ""),
                    "turn": turn.get("turn", ""),
                    "rule_id": score.get("rule_id", ""),
                    "before": bool_text(before),
                    "after": bool_text(after),
                    "ai_action": action,
                    "ai_issue_type": issue_type,
                }
            )

    for record in records:
        for turn in record.get("turn_results", []) or []:
            metrics = compute_turn_metrics(
                turn.get("scores", []),
                turn.get("attack_targets") or record.get("attack_targets", []),
            )
            turn["metrics"] = metrics
            turn["compliance_rate"] = metrics["per_rule_pass_rate"]
        record["judge_status"] = "complete" if count_unresolved_judge_scores([record]) == 0 else "incomplete"

    write_jsonl(out_jsonl, records)
    csv_write(change_csv, changes, CHANGE_FIELDS)
    summary = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "input_jsonl": str(input_path),
        "input_sha256": sha256_file(input_path),
        "label_csv": str(labels_path),
        "label_rows": len(labels),
        "reviewed_score_cells": reviewed_count,
        "changed_score_cells": len(changes),
        "human_only_rows": human_only_count,
        "action_counts": dict(sorted(action_counts.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        "output_jsonl": str(out_jsonl),
        "output_sha256": sha256_file(out_jsonl),
        "change_csv": str(change_csv),
        "unresolved_judge_scores": count_unresolved_judge_scores(records),
        "records": len(records),
        "turns": sum(len(record.get("turn_results", [])) for record in records),
    }
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Q1 all-target AI-adjust helper")
    sub = parser.add_subparsers(dest="command", required=True)

    p_prepare = sub.add_parser("prepare", help="flatten judged JSONL and write audit candidate CSVs")
    p_prepare.add_argument("--input", required=True, help="Judged result JSONL")
    p_prepare.add_argument("--outdir", required=True, help="Output audit-prep directory")
    p_prepare.add_argument("--max-true-per-rule", type=int, default=80)
    p_prepare.add_argument("--max-na-per-rule", type=int, default=80)
    p_prepare.add_argument("--seed", type=int, default=22110157)
    p_prepare.set_defaults(func=prepare)

    p_apply = sub.add_parser("apply", help="apply completed label CSV to a copy of judged JSONL")
    p_apply.add_argument("--input", required=True, help="Judged result JSONL")
    p_apply.add_argument("--labels", required=True, help="Completed label CSV")
    p_apply.add_argument("--output-jsonl", required=True, help="AI-adjusted output JSONL")
    p_apply.add_argument("--change-csv", required=True, help="Score change CSV output")
    p_apply.add_argument("--summary-json", required=True, help="Adjustment summary JSON output")
    p_apply.set_defaults(func=apply_labels)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

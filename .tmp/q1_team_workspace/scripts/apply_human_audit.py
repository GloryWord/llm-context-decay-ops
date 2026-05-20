"""Apply human audit labels to controlled experiment judge scores.

Inputs are the human-review candidate CSV and the three labeling CSVs created
for the controlled local Llama/Gemma run. The script writes:
- a normalized 200-row human audit master CSV,
- a compact score-change CSV,
- a human-adjusted JSONL result file whose per-score ``pass`` values are
  corrected/excluded according to the human labels.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_ROOT = ROOT / "data/outputs/2026-05-11_local_llama_gemma_controlled_v1"
VALID_ACTIONS = {"keep", "override", "exclude", "unsure"}
BOOL_TEXT = {"TRUE", "FALSE"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def norm_bool(value: str | None) -> str:
    value = (value or "").strip().upper()
    if value in {"TRUE", "FALSE", "NA", "NONE"}:
        return "NA" if value == "NONE" else value
    return ""


def bool_from_text(value: str) -> bool | None:
    value = norm_bool(value)
    if value == "TRUE":
        return True
    if value == "FALSE":
        return False
    return None


def normalize_label_row(row: dict[str, str], source_file: str) -> dict[str, str]:
    raw_action = (row.get("human_action") or "").strip()
    raw_reason = (row.get("human_reason") or "").strip()
    action = raw_action
    reason = raw_reason
    shifted = False

    # One labeling sheet accidentally used human_reason for action and
    # human_action for the free-text reason. Normalize without losing raw values.
    if action not in VALID_ACTIONS and raw_reason in VALID_ACTIONS:
        action = raw_reason
        reason = raw_action
        shifted = True

    human_applicable = norm_bool(row.get("human_applicable"))
    human_pass = norm_bool(row.get("human_pass"))
    judge_pass = norm_bool(row.get("judge_pass"))
    explicit = bool(human_applicable or human_pass or raw_action or raw_reason)

    if not explicit:
        action = "keep"
        human_applicable = "TRUE"
        human_pass = judge_pass
        reason = "blank human fields interpreted as judge accepted"
        label_status = "inferred_keep_from_blank"
    else:
        label_status = "explicit_human_label"
        if not action and human_pass in BOOL_TEXT:
            action = "override" if human_pass != judge_pass else "keep"
        if action == "keep" and not human_pass:
            human_pass = judge_pass
        if action == "exclude" or human_applicable == "FALSE":
            action = "exclude"
            human_applicable = human_applicable or "FALSE"
            human_pass = "NA"
        if action == "override" and not human_applicable:
            human_applicable = "TRUE"

    rule_id = (row.get("rule_id_to_review") or row.get("rule_id") or "").strip()
    rule_text = row.get("rule_text_to_review") or row.get("rule_text") or ""
    review_reason = row.get("recommended_review_reason") or row.get("review_reason") or ""

    return {
        "source_file": source_file,
        "review_id": row.get("review_id", ""),
        "label_status": label_status,
        "was_shifted_action_reason": str(shifted).upper(),
        "priority": row.get("priority", ""),
        "review_selection_reason": review_reason,
        "case_id": row.get("case_id", ""),
        "condition": row.get("condition", ""),
        "rule_count": row.get("rule_count", ""),
        "turn_count": row.get("turn_count", ""),
        "turn": row.get("turn", ""),
        "is_final_turn": row.get("is_final_turn", ""),
        "target_rule_id": row.get("target_rule_id", ""),
        "target_rule_category": row.get("target_rule_category", ""),
        "turn_attack_targets": row.get("turn_attack_targets", ""),
        "turn_attack_mode": row.get("turn_attack_mode", ""),
        "is_target_rule_score": row.get("is_target_rule_score", ""),
        "rule_id_to_review": rule_id,
        "rule_category_to_review": row.get("rule_category_to_review") or row.get("rule_category") or "",
        "rule_text_to_review": rule_text,
        "judge_method": row.get("judge_method", ""),
        "judge_pass": row.get("judge_pass", ""),
        "judge_detail": row.get("judge_detail", ""),
        "user_message": row.get("user_message", ""),
        "model_response": row.get("model_response", ""),
        "human_applicable_raw": row.get("human_applicable", ""),
        "human_pass_raw": row.get("human_pass", ""),
        "human_reason_raw": row.get("human_reason", ""),
        "human_action_raw": row.get("human_action", ""),
        "normalized_human_applicable": human_applicable,
        "normalized_human_pass": human_pass,
        "normalized_human_action": action,
        "normalized_human_reason": reason,
    }


def merge_labels(candidate_rows: list[dict[str, str]], label_paths: list[Path]) -> list[dict[str, str]]:
    labels_by_id: dict[str, dict[str, str]] = {}
    for path in label_paths:
        for row in read_csv(path):
            review_id = row.get("review_id", "")
            if not review_id:
                continue
            labels_by_id[review_id] = normalize_label_row(row, path.name)

    candidate_ids = {row["review_id"] for row in candidate_rows}
    missing = sorted(candidate_ids - set(labels_by_id))
    extra = sorted(set(labels_by_id) - candidate_ids)
    if missing or extra:
        raise ValueError(f"Human labels do not match candidates. missing={missing[:10]} extra={extra[:10]}")

    merged: list[dict[str, str]] = []
    for candidate in candidate_rows:
        label = labels_by_id[candidate["review_id"]]
        # Keep every original candidate column, then add normalized human audit
        # columns. This makes the master CSV the single non-lossy audit file.
        merged_row = dict(candidate)
        merged_row.update(
            {
                "source_file": label["source_file"],
                "label_status": label["label_status"],
                "was_shifted_action_reason": label["was_shifted_action_reason"],
                "human_label_source_file": label["source_file"],
                "human_label_status": label["label_status"],
                "human_was_shifted_action_reason": label["was_shifted_action_reason"],
                "review_selection_reason": label["review_selection_reason"],
                "rule_id_to_review": label["rule_id_to_review"] or candidate.get("rule_id", ""),
                "rule_category_to_review": label["rule_category_to_review"] or candidate.get("rule_category", ""),
                "rule_text_to_review": label["rule_text_to_review"] or candidate.get("rule_text", ""),
                "human_applicable_raw": label["human_applicable_raw"],
                "human_pass_raw": label["human_pass_raw"],
                "human_reason_raw": label["human_reason_raw"],
                "human_action_raw": label["human_action_raw"],
                "normalized_human_applicable": label["normalized_human_applicable"],
                "normalized_human_pass": label["normalized_human_pass"],
                "normalized_human_action": label["normalized_human_action"],
                "normalized_human_reason": label["normalized_human_reason"],
            }
        )
        merged.append(merged_row)

    if len({row["review_id"] for row in merged}) != len(merged):
        raise ValueError("Duplicate review_id found after merge")
    return merged

def validate_master(master_rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    for row in master_rows:
        rid = row["review_id"]
        action = row["normalized_human_action"]
        hpass = row["normalized_human_pass"]
        jpass = norm_bool(row["judge_pass"])
        app = row["normalized_human_applicable"]
        if action not in {"keep", "override", "exclude"}:
            errors.append(f"{rid}: invalid action={action!r}")
        if action == "override" and hpass not in BOOL_TEXT:
            errors.append(f"{rid}: override requires TRUE/FALSE human pass, got {hpass!r}")
        if action == "exclude" and hpass != "NA":
            errors.append(f"{rid}: exclude should have NA human pass, got {hpass!r}")
        if action == "keep" and hpass in BOOL_TEXT and jpass in BOOL_TEXT and hpass != jpass:
            errors.append(f"{rid}: keep but human_pass={hpass} differs from judge_pass={jpass}")
        if app not in {"TRUE", "FALSE", "NA", ""}:
            errors.append(f"{rid}: invalid human_applicable={app!r}")
    return errors


def effective_pass(row: dict[str, str], original_pass: bool | None) -> bool | None:
    action = row["normalized_human_action"]
    hpass = row["normalized_human_pass"]
    app = row["normalized_human_applicable"]
    if action == "exclude" or app == "FALSE":
        return None
    if action == "override":
        return bool_from_text(hpass)
    return original_pass


def apply_human_adjustments(
    records_path: Path,
    master_rows: list[dict[str, str]],
    output_jsonl: Path,
    changes_csv: Path,
) -> dict[str, Any]:
    audit_by_key: dict[tuple[str, int, str], dict[str, str]] = {}
    for row in master_rows:
        audit_by_key[(row["case_id"], int(row["turn"]), row["rule_id_to_review"])] = row

    changes: list[dict[str, Any]] = []
    records_written = 0
    reviewed_cells = 0

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with records_path.open("r", encoding="utf-8") as src, output_jsonl.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            record = json.loads(line)
            adjusted = deepcopy(record)
            adjusted["human_audit_applied"] = True
            adjusted["human_audit_source"] = str(output_jsonl.parent.parent / "human_review" / "human_audit_all_200_normalized.csv")
            for turn in adjusted.get("turn_results", []):
                turn_no = int(turn.get("turn", 0))
                for score in turn.get("scores", []):
                    key = (str(adjusted.get("case_id", "")), turn_no, str(score.get("rule_id", "")))
                    audit = audit_by_key.get(key)
                    if audit is None:
                        continue
                    reviewed_cells += 1
                    original = score.get("pass")
                    new_pass = effective_pass(audit, original)
                    changed = new_pass != original
                    score["human_review"] = {
                        "reviewed": True,
                        "review_id": audit["review_id"],
                        "label_status": audit["label_status"],
                        "action": audit["normalized_human_action"],
                        "applicable": audit["normalized_human_applicable"],
                        "human_pass": audit["normalized_human_pass"],
                        "human_reason": audit["normalized_human_reason"],
                        "judge_pass_before_human": original,
                        "adjusted_pass": new_pass,
                        "changed": changed,
                    }
                    score["judge_pass_before_human"] = original
                    score["pass"] = new_pass
                    score["human_adjusted"] = changed
                    if changed:
                        old_detail = score.get("detail", "")
                        score["detail"] = (
                            f"human_adjusted[{audit['normalized_human_action']}]: "
                            f"{audit['normalized_human_reason']} | original: {old_detail}"
                        )
                        changes.append(
                            {
                                "review_id": audit["review_id"],
                                "case_id": adjusted.get("case_id", ""),
                                "condition": adjusted.get("condition", ""),
                                "rule_count": adjusted.get("rule_count", ""),
                                "turn_count": adjusted.get("turn_count", ""),
                                "turn": turn_no,
                                "is_final_turn": str(turn_no == int(adjusted.get("turn_count", 0))).upper(),
                                "target_rule_id": adjusted.get("target_rule_id", ""),
                                "rule_id": score.get("rule_id", ""),
                                "is_target_rule_score": str(score.get("rule_id") == adjusted.get("target_rule_id")).upper(),
                                "human_action": audit["normalized_human_action"],
                                "judge_pass_before_human": original,
                                "human_adjusted_pass": new_pass,
                                "human_reason": audit["normalized_human_reason"],
                            }
                        )
            dst.write(json.dumps(adjusted, ensure_ascii=False) + "\n")
            records_written += 1

    change_fields = [
        "review_id", "case_id", "condition", "rule_count", "turn_count", "turn", "is_final_turn",
        "target_rule_id", "rule_id", "is_target_rule_score", "human_action",
        "judge_pass_before_human", "human_adjusted_pass", "human_reason",
    ]
    write_csv(changes_csv, changes, change_fields)
    return {
        "records_written": records_written,
        "reviewed_score_cells_seen": reviewed_cells,
        "changed_score_cells": len(changes),
        "changes_by_action": Counter(row["human_action"] for row in changes),
        "changes_by_before_after": {
            "|".join(key): value
            for key, value in Counter(
                (str(row["judge_pass_before_human"]), str(row["human_adjusted_pass"])) for row in changes
            ).items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize and apply human audit labels.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()

    output_root = Path(args.output_root)
    review_dir = output_root / "human_review"
    adjusted_dir = output_root / "human_adjusted"
    candidate_path = review_dir / "human_review_candidates_controlled_v1.csv"
    label_paths = [
        review_dir / "human_review_minimum_final_failures_51_labeling_simple.csv",
        review_dir / "human_review_recommended_extra_risk_check_15.csv",
        review_dir / "human_review_remaining_unchecked_134_labeling_simple.csv",
    ]
    records_path = output_root / "reaggregated" / "metrics_enriched_results.jsonl"

    master_path = review_dir / "human_audit_all_200_normalized.csv"
    if all(path.exists() for path in label_paths):
        candidate_rows = read_csv(candidate_path)
        master_rows = merge_labels(candidate_rows, label_paths)
        master_fields = list(master_rows[0].keys())
        write_csv(master_path, master_rows, master_fields)
        label_input_mode = "source_label_csvs"
    elif master_path.exists():
        master_rows = read_csv(master_path)
        candidate_rows = read_csv(candidate_path) if candidate_path.exists() else master_rows
        label_input_mode = "existing_normalized_master_csv"
    else:
        missing = [str(path) for path in label_paths if not path.exists()]
        raise FileNotFoundError(
            "No normalized master CSV found and source label CSVs are missing: " + ", ".join(missing)
        )

    errors = validate_master(master_rows)
    if errors:
        raise ValueError("Human audit validation failed:\n" + "\n".join(errors[:50]))

    explicit_rows = [row for row in master_rows if row["label_status"] == "explicit_human_label"]

    adjusted_jsonl = adjusted_dir / "metrics_enriched_results_human_adjusted.jsonl"
    changes_csv = adjusted_dir / "human_score_changes.csv"
    apply_summary = apply_human_adjustments(records_path, master_rows, adjusted_jsonl, changes_csv)

    summary = {
        "candidate_rows": len(candidate_rows),
        "human_audit_rows": len(master_rows),
        "explicit_human_label_rows": len(explicit_rows),
        "label_status_counts": Counter(row["label_status"] for row in master_rows),
        "action_counts": Counter(row["normalized_human_action"] for row in master_rows),
        "judge_human_pass_counts": {
            "|".join(key): value
            for key, value in Counter(
                (norm_bool(row["judge_pass"]), row["normalized_human_pass"], row["normalized_human_action"])
                for row in master_rows
            ).items()
        },
        **apply_summary,
        "outputs": {
            "master_csv": str(master_path),
            "label_input_mode": label_input_mode,
            "adjusted_jsonl": str(adjusted_jsonl),
            "changes_csv": str(changes_csv),
        },
    }
    summary_path = adjusted_dir / "human_audit_apply_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=lambda x: dict(x)), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=lambda x: dict(x)))


if __name__ == "__main__":
    main()

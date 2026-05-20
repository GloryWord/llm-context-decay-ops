"""Export OpenRouter Q2 frontier target responses to a human-labeling CSV.

Input is the JSONL produced by ``scripts/run_frontier_q2_openrouter.py``.
Output is one row per model/scenario response, with blank human-label columns.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


FIELDNAMES = [
    "request_id",
    "model_name",
    "scenario_id",
    "research_question",
    "system_prompt_profile",
    "turn_count",
    "system_rule_set",
    "target_rule_id",
    "target_rule_category",
    "target_rule_text",
    "attack_type",
    "attack_scope",
    "max_tokens",
    "temperature",
    "system_prompt",
    "input",
    "output",
    "finish_reason",
    "http_status",
    "usage_prompt_tokens",
    "usage_completion_tokens",
    "usage_total_tokens",
    "human_target_rule_pass",
    "human_perfect_success",
    "human_non_target_failure",
    "human_notes",
    "system_prompt_sha256",
    "input_sha256",
]


def usage_value(record: dict[str, Any], *keys: str) -> Any:
    usage = record.get("usage") or {}
    for key in keys:
        if key in usage:
            return usage[key]
    return ""


def convert(input_jsonl: Path, output_csv: Path) -> int:
    latest_by_request_id: dict[str, dict[str, Any]] = {}
    with input_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            request_id = record.get("request_id", "")
            if not request_id:
                continue
            latest_by_request_id[request_id] = (
                {
                    "request_id": request_id,
                    "model_name": record.get("target_model", ""),
                    "scenario_id": record.get("scenario_id", ""),
                    "research_question": record.get("research_question", ""),
                    "system_prompt_profile": record.get("system_prompt_profile", ""),
                    "turn_count": record.get("turn_count", ""),
                    "system_rule_set": record.get("system_rule_set", ""),
                    "target_rule_id": record.get("target_rule_id", ""),
                    "target_rule_category": record.get("target_rule_category", ""),
                    "target_rule_text": record.get("target_rule_text", ""),
                    "attack_type": record.get("attack_type", ""),
                    "attack_scope": record.get("attack_scope", ""),
                    "max_tokens": record.get("max_tokens", ""),
                    "temperature": record.get("temperature", ""),
                    "system_prompt": record.get("system_prompt_text", ""),
                    "input": record.get("prompt_text", ""),
                    "output": record.get("response", ""),
                    "finish_reason": record.get("finish_reason", ""),
                    "http_status": record.get("http_status", ""),
                    "usage_prompt_tokens": usage_value(record, "prompt_tokens", "input_tokens"),
                    "usage_completion_tokens": usage_value(
                        record, "completion_tokens", "output_tokens"
                    ),
                    "usage_total_tokens": usage_value(record, "total_tokens"),
                    "human_target_rule_pass": "",
                    "human_perfect_success": "",
                    "human_non_target_failure": "",
                    "human_notes": "",
                    "system_prompt_sha256": record.get("system_prompt_sha256", ""),
                    "input_sha256": record.get("prompt_sha256", ""),
                }
            )
    rows = list(latest_by_request_id.values())

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_jsonl", type=Path)
    parser.add_argument("output_csv", type=Path)
    args = parser.parse_args()
    count = convert(args.input_jsonl, args.output_csv)
    print(f"Wrote {count} rows to {args.output_csv}")


if __name__ == "__main__":
    main()

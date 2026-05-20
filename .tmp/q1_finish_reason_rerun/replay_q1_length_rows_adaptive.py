#!/usr/bin/env python3
"""Adaptive rerun for Q1 rows that were previously cut by max_tokens=512.

This script intentionally targets only the authoritative clean rerun rows whose
OpenAI/vLLM metadata showed `finish_reason=length` and `completion_tokens=512`.
It reruns each target with a bounded token-cap ladder and stops per row as soon
as the model/server returns a non-length finish reason, preserving raw metadata
for thesis provenance.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import replay_q1_turns_with_metadata as base  # noqa: E402

DEFAULT_SOURCE = THIS_DIR / "clean_n83_20260518T191600+0900" / "replay_metadata_r07_false_truncation_suspect.jsonl"


def parse_caps(raw: str) -> list[int]:
    caps = [int(x.strip()) for x in raw.split(",") if x.strip()]
    if not caps:
        raise ValueError("at least one cap required")
    if caps != sorted(caps):
        raise ValueError("caps must be ascending")
    if any(c <= 512 for c in caps):
        raise ValueError("adaptive caps must be > 512 for this rerun")
    return caps


def load_source_targets(path: Path) -> list[dict[str, Any]]:
    rows = base.load_jsonl(path)
    targets: list[dict[str, Any]] = []
    for row in rows:
        usage = row.get("usage") or {}
        max_tokens = row.get("max_tokens")
        completion_tokens = usage.get("completion_tokens")
        if (
            row.get("ok") is True
            and row.get("finish_reason") == "length"
            and max_tokens == 512
            and completion_tokens == 512
        ):
            targets.append(row)
    targets.sort(key=lambda r: (str(r.get("case_id")), int(r.get("turn", 0)), int(r.get("index", 0))))
    return targets


def shard_targets(targets: list[dict[str, Any]], shard_index: int, shard_count: int) -> list[dict[str, Any]]:
    if shard_count < 1:
        raise ValueError("shard_count must be >= 1")
    if not (0 <= shard_index < shard_count):
        raise ValueError("shard_index must satisfy 0 <= index < count")
    return [row for pos, row in enumerate(targets) if pos % shard_count == shard_index]


def find_original(records_by_case: dict[str, dict[str, Any]], case_id: str, turn_no: int) -> tuple[dict[str, Any], dict[str, Any]]:
    record = records_by_case[case_id]
    for turn in record.get("turn_results", []):
        if int(turn.get("turn")) == turn_no:
            return record, turn
    raise KeyError(f"missing turn {turn_no} for {case_id}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-metadata", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--cases", type=Path, default=base.DEFAULT_CASES)
    ap.add_argument("--results", type=Path, default=base.DEFAULT_RESULTS)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--api-url", default=os.getenv("VLLM_API_URL", base.DEFAULT_API_URL))
    ap.add_argument("--model", default=os.getenv("EVAL_MODEL_NAME", base.DEFAULT_MODEL))
    ap.add_argument("--api-key", default=os.getenv("VLLM_API_KEY", ""))
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--caps", default="1024,1536,2048,3072")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--shard-index", type=int, default=0)
    ap.add_argument("--shard-count", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    caps = parse_caps(args.caps)
    all_targets = load_source_targets(args.source_metadata)
    targets = shard_targets(all_targets, args.shard_index, args.shard_count)
    if args.limit:
        targets = targets[: args.limit]

    args.outdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "purpose": "Q1 R07 max-token truncation disambiguation",
        "source_metadata": str(args.source_metadata),
        "source_target_count_length512": len(all_targets),
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "target_count": len(targets),
        "cases_file": str(args.cases),
        "results_file": str(args.results),
        "api_url": args.api_url,
        "model": args.model,
        "temperature": args.temperature,
        "caps": caps,
        "dry_run": args.dry_run,
    }
    manifest_path = args.outdir / f"manifest_shard{args.shard_index}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    if args.dry_run:
        return 0

    cases = {r["case_id"]: r for r in base.load_jsonl(args.cases)}
    records = base.load_jsonl(args.results)
    records_by_case = {str(r["case_id"]): r for r in records}

    attempts_path = args.outdir / f"attempts_shard{args.shard_index}.jsonl"
    final_path = args.outdir / f"final_shard{args.shard_index}.jsonl"
    final_rows: list[dict[str, Any]] = []
    errors = 0

    with attempts_path.open("w", encoding="utf-8") as attempts_out, final_path.open("w", encoding="utf-8") as final_out:
        for local_index, src in enumerate(targets, start=1):
            cid = str(src["case_id"])
            turn_no = int(src["turn"])
            record, original_turn = find_original(records_by_case, cid, turn_no)
            case = cases[cid]
            messages = base.build_messages(case, record, turn_no)
            final: dict[str, Any] | None = None
            attempt_count = 0
            for cap in caps:
                attempt_count += 1
                payload = {
                    "model": args.model,
                    "messages": messages,
                    "temperature": args.temperature,
                    "max_tokens": cap,
                }
                started = time.time()
                try:
                    raw = base.post_chat(args.api_url, args.api_key, payload, args.timeout)
                    choice = (raw.get("choices") or [{}])[0]
                    replay_response = ((choice.get("message") or {}).get("content") or "")
                    usage = raw.get("usage") or {}
                    row = {
                        "ok": True,
                        "case_id": cid,
                        "turn": turn_no,
                        "source_index": src.get("index"),
                        "local_index": local_index,
                        "shard_index": args.shard_index,
                        "shard_count": args.shard_count,
                        "attempt_no": attempt_count,
                        "max_tokens": cap,
                        "finish_reason": choice.get("finish_reason"),
                        "usage": usage,
                        "hit_max_tokens": choice.get("finish_reason") == "length" or usage.get("completion_tokens") == cap,
                        "model_requested": args.model,
                        "model_returned": raw.get("model"),
                        "api_url": args.api_url,
                        "temperature": args.temperature,
                        "response": replay_response,
                        "response_length": len(replay_response),
                        "response_tail": replay_response[-500:],
                        "original_512_finish_reason": src.get("finish_reason"),
                        "original_512_completion_tokens": (src.get("usage") or {}).get("completion_tokens"),
                        "original_512_response_equals_original": src.get("response_equals_original"),
                        "original_512_response_tail": src.get("replay_response_tail"),
                        "original_experiment_response_length": len(str(original_turn.get("response", ""))),
                        "original_experiment_response_tail": str(original_turn.get("response", ""))[-500:],
                        "user_message": original_turn.get("user_message"),
                        "attack_mode": original_turn.get("attack_mode"),
                        "target_rule_id": record.get("target_rule_id"),
                        "rule_count": record.get("rule_count"),
                        "turn_count": record.get("turn_count"),
                        "condition": record.get("condition"),
                        "attack_order_variant": record.get("attack_order_variant"),
                        "r07_original_detail": (base.get_score(original_turn, "R07") or {}).get("detail"),
                        "r07_original_ai_review": (base.get_score(original_turn, "R07") or {}).get("ai_review"),
                        "messages_sha256": base.sha256_text(json.dumps(messages, ensure_ascii=False, sort_keys=True)),
                        "system_prompt_sha256": base.sha256_text(case["system_prompt"]),
                        "elapsed_s": round(time.time() - started, 3),
                        "raw_response_id": raw.get("id"),
                        "raw_created": raw.get("created"),
                    }
                except Exception as exc:
                    row = {
                        "ok": False,
                        "case_id": cid,
                        "turn": turn_no,
                        "source_index": src.get("index"),
                        "local_index": local_index,
                        "shard_index": args.shard_index,
                        "shard_count": args.shard_count,
                        "attempt_no": attempt_count,
                        "max_tokens": cap,
                        "error": repr(exc),
                        "elapsed_s": round(time.time() - started, 3),
                    }
                attempts_out.write(json.dumps(row, ensure_ascii=False) + "\n")
                attempts_out.flush()
                print(f"[shard {args.shard_index} {local_index}/{len(targets)} cap={cap}] {cid} t{turn_no} ok={row.get('ok')} finish={row.get('finish_reason')} usage={row.get('usage')}", flush=True)
                final = row
                if not row.get("ok"):
                    errors += 1
                    break
                if row.get("finish_reason") != "length" and not row.get("hit_max_tokens"):
                    break
            assert final is not None
            final = dict(final)
            final["attempt_count"] = attempt_count
            final["adaptive_caps"] = caps
            final["resolved_non_length"] = bool(final.get("ok") and final.get("finish_reason") != "length" and not final.get("hit_max_tokens"))
            final["still_cap_limited_at_final_cap"] = bool(final.get("ok") and (final.get("finish_reason") == "length" or final.get("hit_max_tokens")))
            final_out.write(json.dumps(final, ensure_ascii=False) + "\n")
            final_out.flush()
            final_rows.append(final)

    final_finish_counts = collections.Counter(str(r.get("finish_reason")) for r in final_rows)
    cap_counts = collections.Counter(str(r.get("max_tokens")) for r in final_rows)
    attempt_counts = collections.Counter(str(r.get("attempt_count")) for r in final_rows)
    summary = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "purpose": "Q1 R07 max-token truncation disambiguation",
        "source_metadata": str(args.source_metadata),
        "source_target_count_length512": len(all_targets),
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "target_count": len(targets),
        "ok_count": sum(1 for r in final_rows if r.get("ok")),
        "error_count": sum(1 for r in final_rows if not r.get("ok")),
        "transport_error_count": errors,
        "final_finish_reason_counts": dict(final_finish_counts),
        "final_cap_counts": dict(cap_counts),
        "attempt_count_distribution": dict(attempt_counts),
        "resolved_non_length_count": sum(1 for r in final_rows if r.get("resolved_non_length")),
        "still_cap_limited_at_final_cap_count": sum(1 for r in final_rows if r.get("still_cap_limited_at_final_cap")),
        "caps": caps,
        "attempts_jsonl": str(attempts_path),
        "final_jsonl": str(final_path),
        "manifest": str(manifest_path),
    }
    summary_path = args.outdir / f"summary_shard{args.shard_index}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if summary["error_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

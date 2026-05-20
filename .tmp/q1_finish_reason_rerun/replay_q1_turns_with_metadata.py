#!/usr/bin/env python3
"""Replay selected Q1 turns and persist OpenAI/vLLM raw completion metadata.

This intentionally does not overwrite experiment outputs. It reconstructs the
conversation up to a selected turn from:
  - the original case system prompt/user messages, and
  - saved prior assistant responses in the original result JSONL.
Then it sends exactly one target-model request for that selected turn and saves
finish_reason + usage for thesis provenance checks.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES = ROOT / "data/processed/q1_sampled_q2_injection_cases.jsonl"
DEFAULT_RESULTS = ROOT / "data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4_ai_adjusted.jsonl"
DEFAULT_OUTDIR = ROOT / ".tmp/q1_finish_reason_rerun"
DEFAULT_API_URL = "http://210.179.28.26:18000/v1/chat/completions"
DEFAULT_MODEL = "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4"

TRUNCATION_DETAIL_RE = re.compile(
    r"(끊|중간|중단|truncat|incomplete|cut off|abrupt)",
    re.IGNORECASE,
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def get_score(turn: dict[str, Any], rule_id: str) -> dict[str, Any] | None:
    for score in turn.get("scores", []):
        if score.get("rule_id") == rule_id:
            return score
    return None


def tail_mid_sentence(text: str) -> bool:
    """Conservative abrupt-tail heuristic used for the N=83 rerun cohort."""
    tail = (text or "").strip()
    complete_end = set('.!?。！？다요죠함음임됨"\')]）】》')
    return bool(tail) and tail[-1] not in complete_end


def select_targets(records: list[dict[str, Any]], selector: str) -> list[tuple[str, int, dict[str, Any], dict[str, Any], dict[str, Any]]]:
    selected: list[tuple[str, int, dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for rec in records:
        for turn in rec.get("turn_results", []):
            score = get_score(turn, "R07")
            if not score:
                continue
            include = False
            if selector == "q1samp_00020_turn15":
                include = rec.get("case_id") == "q1samp_00020" and int(turn.get("turn")) == 15
            elif selector == "r07_false":
                include = score.get("pass") is False
            elif selector == "r07_false_truncation_detail":
                detail_blob = f"{score.get('detail','')}"
                include = score.get("pass") is False and bool(TRUNCATION_DETAIL_RE.search(detail_blob))
            elif selector == "r07_false_tail_mid_sentence":
                include = score.get("pass") is False and tail_mid_sentence(str(turn.get("response", "")))
            elif selector == "r07_false_truncation_suspect":
                detail_blob = f"{score.get('detail','')}"
                include = score.get("pass") is False and (
                    bool(TRUNCATION_DETAIL_RE.search(detail_blob))
                    or tail_mid_sentence(str(turn.get("response", "")))
                )
            else:
                raise ValueError(f"unknown selector: {selector}")
            if include:
                selected.append((str(rec["case_id"]), int(turn["turn"]), rec, turn, score))
    selected.sort(key=lambda x: (x[0], x[1]))
    return selected


def build_messages(case: dict[str, Any], record: dict[str, Any], target_turn: int) -> list[dict[str, str]]:
    conv = {int(t["turn"]): t for t in case["conversation_template"]}
    prior_results = {int(t["turn"]): t for t in record.get("turn_results", [])}
    messages: list[dict[str, str]] = [{"role": "system", "content": case["system_prompt"]}]
    for turn_no in range(1, target_turn):
        if turn_no not in conv or turn_no not in prior_results:
            raise KeyError(f"missing prior turn {turn_no} for {case.get('case_id')}")
        messages.append({"role": "user", "content": conv[turn_no]["content"]})
        messages.append({"role": "assistant", "content": prior_results[turn_no]["response"]})
    if target_turn not in conv:
        raise KeyError(f"missing target user turn {target_turn} for {case.get('case_id')}")
    messages.append({"role": "user", "content": conv[target_turn]["content"]})
    return messages


def post_chat(api_url: str, api_key: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(api_url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def write_candidate_csv(path: Path, targets: list[tuple[str, int, dict[str, Any], dict[str, Any], dict[str, Any]]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case_id", "turn", "condition", "rule_count", "turn_count", "target_rule_id",
                "attack_mode", "attack_order_variant", "response_length", "r07_detail",
                "r07_ai_issue_type", "r07_ai_reason_ko", "tail_mid_sentence", "user_message",
                "response_tail",
            ],
        )
        writer.writeheader()
        for cid, turn_no, rec, turn, score in targets:
            ai = score.get("ai_review", {}) or {}
            writer.writerow({
                "case_id": cid,
                "turn": turn_no,
                "condition": rec.get("condition"),
                "rule_count": rec.get("rule_count"),
                "turn_count": rec.get("turn_count"),
                "target_rule_id": rec.get("target_rule_id"),
                "attack_mode": turn.get("attack_mode"),
                "attack_order_variant": rec.get("attack_order_variant"),
                "response_length": turn.get("response_length"),
                "r07_detail": score.get("detail", ""),
                "r07_ai_issue_type": ai.get("ai_issue_type", ""),
                "r07_ai_reason_ko": ai.get("ai_reason_ko", ""),
                "tail_mid_sentence": tail_mid_sentence(str(turn.get("response", ""))),
                "user_message": turn.get("user_message", ""),
                "response_tail": str(turn.get("response", ""))[-160:],
            })


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    ap.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    ap.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    ap.add_argument("--selector", choices=["q1samp_00020_turn15", "r07_false", "r07_false_truncation_detail", "r07_false_tail_mid_sentence", "r07_false_truncation_suspect"], default="q1samp_00020_turn15")
    ap.add_argument("--api-url", default=os.getenv("VLLM_API_URL", DEFAULT_API_URL))
    ap.add_argument("--model", default=os.getenv("EVAL_MODEL_NAME", DEFAULT_MODEL))
    ap.add_argument("--api-key", default=os.getenv("VLLM_API_KEY", ""))
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--limit", type=int, default=0, help="optional first-N limit after selection")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    cases = {r["case_id"]: r for r in load_jsonl(args.cases)}
    records = load_jsonl(args.results)
    targets = select_targets(records, args.selector)
    if args.limit:
        targets = targets[: args.limit]

    candidate_csv = args.outdir / f"candidates_{args.selector}.csv"
    write_candidate_csv(candidate_csv, targets)

    manifest = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "selector": args.selector,
        "target_count": len(targets),
        "cases_file": str(args.cases),
        "results_file": str(args.results),
        "candidate_csv": str(candidate_csv),
        "api_url": args.api_url,
        "model": args.model,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "dry_run": args.dry_run,
    }
    (args.outdir / f"manifest_{args.selector}.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

    if args.dry_run:
        return 0

    output_jsonl = args.outdir / f"replay_metadata_{args.selector}.jsonl"
    summary_rows: list[dict[str, Any]] = []
    with output_jsonl.open("w", encoding="utf-8") as out:
        for idx, (cid, turn_no, rec, turn, score) in enumerate(targets, start=1):
            case = cases[cid]
            messages = build_messages(case, rec, turn_no)
            payload = {
                "model": args.model,
                "messages": messages,
                "temperature": args.temperature,
                "max_tokens": args.max_tokens,
            }
            started = time.time()
            try:
                raw = post_chat(args.api_url, args.api_key, payload, args.timeout)
                choice = (raw.get("choices") or [{}])[0]
                replay_response = ((choice.get("message") or {}).get("content") or "")
                row = {
                    "ok": True,
                    "selector": args.selector,
                    "index": idx,
                    "case_id": cid,
                    "turn": turn_no,
                    "model_requested": args.model,
                    "api_url": args.api_url,
                    "temperature": args.temperature,
                    "max_tokens": args.max_tokens,
                    "finish_reason": choice.get("finish_reason"),
                    "usage": raw.get("usage"),
                    "model_returned": raw.get("model"),
                    "response": replay_response,
                    "response_length": len(replay_response),
                    "original_response_length": len(str(turn.get("response", ""))),
                    "response_equals_original": replay_response == turn.get("response"),
                    "original_response_tail": str(turn.get("response", ""))[-240:],
                    "replay_response_tail": replay_response[-240:],
                    "r07_detail": score.get("detail"),
                    "r07_ai_review": score.get("ai_review"),
                    "messages_sha256": sha256_text(json.dumps(messages, ensure_ascii=False, sort_keys=True)),
                    "system_prompt_sha256": sha256_text(case["system_prompt"]),
                    "prior_turns_from_saved_result": turn_no - 1,
                    "elapsed_s": round(time.time() - started, 3),
                    "raw_response_id": raw.get("id"),
                    "raw_created": raw.get("created"),
                }
            except Exception as exc:
                row = {
                    "ok": False,
                    "selector": args.selector,
                    "index": idx,
                    "case_id": cid,
                    "turn": turn_no,
                    "model_requested": args.model,
                    "api_url": args.api_url,
                    "temperature": args.temperature,
                    "max_tokens": args.max_tokens,
                    "error": repr(exc),
                    "elapsed_s": round(time.time() - started, 3),
                }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            summary_rows.append(row)
            print(f"[{idx}/{len(targets)}] {cid} turn {turn_no}: ok={row.get('ok')} finish={row.get('finish_reason')} usage={row.get('usage')}", flush=True)

    summary = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "selector": args.selector,
        "target_count": len(targets),
        "ok_count": sum(1 for r in summary_rows if r.get("ok")),
        "error_count": sum(1 for r in summary_rows if not r.get("ok")),
        "finish_reason_counts": {},
        "hit_max_tokens_count": 0,
        "output_jsonl": str(output_jsonl),
        "candidate_csv": str(candidate_csv),
    }
    for row in summary_rows:
        fr = row.get("finish_reason")
        summary["finish_reason_counts"][str(fr)] = summary["finish_reason_counts"].get(str(fr), 0) + 1
        usage = row.get("usage") or {}
        if row.get("ok") and (fr == "length" or usage.get("completion_tokens") == args.max_tokens):
            summary["hit_max_tokens_count"] += 1
    (args.outdir / f"summary_{args.selector}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["error_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

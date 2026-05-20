"""Run Q2-only frontier target-model single-turn requests through OpenRouter.

This runner is intentionally separate from the main local Llama Q1/Q3 runners.
It enforces the Q2-only design:

- one clean API call per scenario/model pair;
- no multi-turn context accumulation;
- no context sharing between implicit_attack and adversarial_attack rows;
- per-case max_tokens, with long-output R07 receiving a larger budget.

By default, use ``--dry-run`` first. Actual OpenRouter completion calls require
``--execute`` and ``OPENROUTER_API_KEY``.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.utils.http_headers import build_json_headers

LOGGER = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_INPUT_CSV = (
    ROOT / "data" / "annotations" / "frontier_q2_general_ai_single_turn_scenarios_final.csv"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "data"
    / "outputs"
    / f"{datetime.now().strftime('%Y-%m-%d')}_openrouter_frontier_q2_single_turn"
)

DEFAULT_MODELS = [
    "moonshotai/kimi-k2.6",
    "qwen/qwen3.6-max-preview",
    "google/gemini-3.1-pro-preview",
    "anthropic/claude-opus-4.7",
]

REQUIRED_COLUMNS = {
    "scenario_id",
    "research_question",
    "system_prompt_profile",
    "use_for_frontier_q2",
    "use_for_q3_aux",
    "turn_count",
    "system_rule_set",
    "system_prompt_text",
    "target_rule_id",
    "target_rule_category",
    "target_rule_text",
    "attack_type",
    "attack_scope",
    "prompt_text",
    "is_valid_prompt",
}


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def model_slug(model: str) -> str:
    return model.replace("/", "__").replace(":", "_")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def request_id_for(scenario_id: str, model: str) -> str:
    return f"{scenario_id}__{model_slug(model)}"


def load_scenarios(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - fields)
        if missing:
            raise ValueError(f"{path} is missing required columns: {missing}")
        rows = list(reader)

    selected: list[dict[str, str]] = []
    for row in rows:
        if row.get("is_valid_prompt", "").strip().lower() == "no":
            continue
        if row.get("use_for_frontier_q2", "").strip().lower() != "yes":
            continue
        selected.append(row)

    return selected


def validate_q2_only_scenarios(rows: list[dict[str, str]], no_system_prompt: bool = False) -> None:
    if not rows:
        raise ValueError("No valid Q2 frontier scenarios found.")

    for row in rows:
        sid = row["scenario_id"]
        expected_profile = "no_system_baseline" if no_system_prompt else "general_ai_q2_only"
        if row.get("system_prompt_profile") != expected_profile:
            raise ValueError(f"{sid}: expected system_prompt_profile={expected_profile}")
        if row.get("use_for_q3_aux") != "no":
            raise ValueError(f"{sid}: Q2 frontier file must not be marked for Q3 aux")
        if row.get("turn_count") != "1":
            raise ValueError(f"{sid}: Q2 frontier run must be single-turn")
        if row.get("attack_scope") != "single_rule":
            raise ValueError(f"{sid}: attack_scope must be single_rule")
        if no_system_prompt:
            if row.get("system_rule_set", ""):
                raise ValueError(f"{sid}: no-system baseline must have empty system_rule_set")
            if row.get("system_prompt_text", ""):
                raise ValueError(f"{sid}: no-system baseline must have empty system_prompt_text")
        else:
            if "R08" in row.get("system_rule_set", ""):
                raise ValueError(f"{sid}: Q2-only system_rule_set must not contain R08")
            if "R08" in row.get("system_prompt_text", ""):
                raise ValueError(f"{sid}: Q2-only system_prompt_text must not contain R08")
        if not row.get("prompt_text", "").strip():
            raise ValueError(f"{sid}: prompt_text is empty")
        if row.get("attack_type") not in {"implicit_attack", "adversarial_attack"}:
            raise ValueError(f"{sid}: unexpected attack_type={row.get('attack_type')!r}")


def max_tokens_for_case(
    row: dict[str, str],
    default_max_tokens: int,
    r07_max_tokens: int,
) -> int:
    if row.get("target_rule_id") == "R07":
        return r07_max_tokens
    return default_max_tokens


def build_clean_messages(row: dict[str, str], no_system_prompt: bool = False) -> list[dict[str, str]]:
    """Return a fresh single-scenario context.

    Normal Q2 requests contain exactly one system message and one user message.
    No-system baselines intentionally contain exactly one user message so target
    model native safety behavior can be measured without project rules.
    """
    if no_system_prompt:
        messages = [{"role": "user", "content": row["prompt_text"]}]
        if len(messages) != 1 or messages[0]["role"] != "user":
            raise AssertionError("No-system frontier request must contain exactly one user message")
        return messages

    messages = [
        {"role": "system", "content": row["system_prompt_text"]},
        {"role": "user", "content": row["prompt_text"]},
    ]
    if len(messages) != 2 or [m["role"] for m in messages] != ["system", "user"]:
        raise AssertionError("Q2 frontier request must contain exactly system+user messages")
    return messages


def build_payload(
    row: dict[str, str],
    model: str,
    temperature: float,
    default_max_tokens: int,
    r07_max_tokens: int,
    reasoning_effort: str | None,
    reasoning_exclude: bool,
    no_system_prompt: bool = False,
) -> dict[str, Any]:
    messages = build_clean_messages(row, no_system_prompt=no_system_prompt)
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens_for_case(row, default_max_tokens, r07_max_tokens),
    }
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}
        if reasoning_exclude:
            payload["reasoning"]["exclude"] = True
    elif reasoning_exclude:
        payload["reasoning"] = {"exclude": True}
    return payload


def has_usable_response(record: dict[str, Any]) -> bool:
    """Return True only when a prior record has target output worth labeling."""
    if record.get("status") != "ok":
        return False
    response = record.get("response")
    return isinstance(response, str) and bool(response.strip())


def load_completed(output_path: Path) -> set[str]:
    completed: set[str] = set()
    if not output_path.exists():
        return completed
    with output_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if has_usable_response(record) and record.get("request_id"):
                completed.add(record["request_id"])
    return completed


async def call_openrouter(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    payload: dict[str, Any],
    max_retries: int,
) -> tuple[dict[str, Any], float]:
    start = time.monotonic()
    for attempt in range(max_retries):
        try:
            async with session.post(OPENROUTER_API_URL, headers=headers, json=payload) as resp:
                text = await resp.text()
                elapsed_ms = (time.monotonic() - start) * 1000
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    data = {"raw_text": text}

                if resp.status == 429 and attempt < max_retries - 1:
                    wait_s = min(60, 5 * (2**attempt))
                    LOGGER.warning("Rate limited; waiting %ss before retry", wait_s)
                    await asyncio.sleep(wait_s)
                    continue
                if resp.status >= 500 and attempt < max_retries - 1:
                    wait_s = min(60, 3 * (2**attempt))
                    LOGGER.warning("Server error %s; waiting %ss before retry", resp.status, wait_s)
                    await asyncio.sleep(wait_s)
                    continue

                return {"http_status": resp.status, "body": data}, elapsed_ms
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            if attempt >= max_retries - 1:
                elapsed_ms = (time.monotonic() - start) * 1000
                return {
                    "http_status": None,
                    "body": {"error": {"message": f"{type(exc).__name__}: {exc}"}},
                }, elapsed_ms
            wait_s = min(60, 3 * (2**attempt))
            LOGGER.warning("Request failed; waiting %ss before retry: %s", wait_s, exc)
            await asyncio.sleep(wait_s)

    elapsed_ms = (time.monotonic() - start) * 1000
    return {"http_status": None, "body": {"error": {"message": "unreachable retry state"}}}, elapsed_ms


def make_record(
    row: dict[str, str],
    model: str,
    temperature: float,
    payload: dict[str, Any],
    api_result: dict[str, Any] | None,
    elapsed_ms: float | None,
    dry_run: bool,
    no_system_prompt: bool = False,
) -> dict[str, Any]:
    request_id = request_id_for(row["scenario_id"], model)
    messages = payload["messages"]
    system_prompt_text = "" if no_system_prompt else row["system_prompt_text"]
    clean_session_assertion = (
        "Each request contains only this scenario's user prompt; no system prompt is sent."
        if no_system_prompt
        else (
            "Each request contains only this scenario's system prompt and user prompt; "
            "implicit/adversarial rows are separate API calls."
        )
    )
    record: dict[str, Any] = {
        "request_id": request_id,
        "scenario_id": row["scenario_id"],
        "research_question": row["research_question"],
        "system_prompt_profile": row["system_prompt_profile"],
        "q2_only_change_note": row.get("q2_only_change_note", ""),
        "target_model": model,
        "temperature": temperature,
        "max_tokens": payload["max_tokens"],
        "message_count": len(messages),
        "clean_session": True,
        "clean_session_assertion": clean_session_assertion,
        "turn_count": int(row["turn_count"]),
        "system_rule_set": row["system_rule_set"],
        "target_rule_id": row["target_rule_id"],
        "target_rule_category": row["target_rule_category"],
        "target_rule_text": row["target_rule_text"],
        "attack_type": row["attack_type"],
        "attack_scope": row["attack_scope"],
        "system_prompt_text": system_prompt_text,
        "prompt_text": row["prompt_text"],
        "system_prompt_sha256": sha256_text(system_prompt_text),
        "prompt_sha256": sha256_text(row["prompt_text"]),
        "dry_run": dry_run,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    if dry_run:
        record["status"] = "planned"
        return record

    assert api_result is not None
    body = api_result["body"]
    status = api_result["http_status"]
    record["http_status"] = status
    record["latency_ms"] = round(elapsed_ms or 0.0, 2)
    record["raw_response"] = body
    record["usage"] = body.get("usage", {}) if isinstance(body, dict) else {}
    if isinstance(body, dict) and body.get("choices"):
        record["response"] = body["choices"][0].get("message", {}).get("content", "")
        record["finish_reason"] = body["choices"][0].get("finish_reason")
        record["status"] = "ok"
    else:
        record["response"] = ""
        record["finish_reason"] = None
        record["status"] = "error"
        record["error"] = body.get("error", body) if isinstance(body, dict) else body
    return record


async def run(args: argparse.Namespace) -> None:
    input_csv = Path(args.input_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / ("planned_requests.jsonl" if args.dry_run else "raw_target_responses.jsonl")

    rows = load_scenarios(input_csv)
    validate_q2_only_scenarios(rows, no_system_prompt=args.no_system_prompt)
    if args.limit:
        rows = rows[: args.limit]

    models = args.models
    completed = set() if args.overwrite or args.dry_run else load_completed(output_path)
    work = [
        (row, model)
        for model in models
        for row in rows
        if request_id_for(row["scenario_id"], model) not in completed
    ]

    LOGGER.info(
        "Q2 frontier run plan: %d scenarios × %d models = %d requests; dry_run=%s",
        len(rows),
        len(models),
        len(work),
        args.dry_run,
    )
    LOGGER.info("Output: %s", output_path)

    run_config = {
        "input_csv": str(input_csv),
        "output_path": str(output_path),
        "models": models,
        "temperature": args.temperature,
        "default_max_tokens": args.default_max_tokens,
        "r07_max_tokens": args.r07_max_tokens,
        "reasoning_effort": args.reasoning_effort,
        "reasoning_exclude": args.reasoning_exclude,
        "concurrency": args.concurrency,
        "dry_run": args.dry_run,
        "no_system_prompt": args.no_system_prompt,
        "clean_session_contract": (
            "Every scenario/model pair is sent as an independent OpenRouter chat "
            "completion request with exactly one user message and no system prompt."
            if args.no_system_prompt
            else (
                "Every scenario/model pair is sent as an independent OpenRouter chat "
                "completion request with exactly two messages: system and user."
            )
        ),
        "scenario_count": len(rows),
        "request_count": len(work),
    }
    with (output_dir / "run_config.json").open("w", encoding="utf-8") as f:
        json.dump(run_config, f, ensure_ascii=False, indent=2)

    if args.dry_run:
        with output_path.open("w", encoding="utf-8") as f:
            for row, model in work:
                payload = build_payload(
                    row,
                    model,
                    args.temperature,
                    args.default_max_tokens,
                    args.r07_max_tokens,
                    args.reasoning_effort,
                    args.reasoning_exclude,
                    args.no_system_prompt,
                )
                record = make_record(
                    row, model, args.temperature, payload, None, None, True, args.no_system_prompt
                )
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        LOGGER.info("Dry-run plan written.")
        return

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required for --execute")

    headers = build_json_headers(OPENROUTER_API_URL, api_key)
    semaphore = asyncio.Semaphore(args.concurrency)
    write_lock = asyncio.Lock()
    timeout = aiohttp.ClientTimeout(total=args.timeout_seconds, connect=30)

    async with aiohttp.ClientSession(timeout=timeout) as session:

        async def bounded(row: dict[str, str], model: str) -> None:
            payload = build_payload(
                row,
                model,
                args.temperature,
                args.default_max_tokens,
                args.r07_max_tokens,
                args.reasoning_effort,
                args.reasoning_exclude,
                args.no_system_prompt,
            )
            async with semaphore:
                api_result, elapsed_ms = await call_openrouter(
                    session, headers, payload, args.max_retries
                )
            record = make_record(
                row, model, args.temperature, payload, api_result, elapsed_ms, False, args.no_system_prompt
            )
            async with write_lock:
                with output_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            if record["status"] == "ok":
                LOGGER.info("OK %s", record["request_id"])
            else:
                LOGGER.error("ERROR %s: %s", record["request_id"], record.get("error"))

        await asyncio.gather(*(bounded(row, model) for row, model in work))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", default=str(DEFAULT_INPUT_CSV))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--default-max-tokens", type=int, default=1024)
    parser.add_argument("--r07-max-tokens", type=int, default=32768)
    parser.add_argument(
        "--reasoning-effort",
        choices=["xhigh", "high", "medium", "low", "minimal", "none"],
        default=None,
        help="Optional OpenRouter reasoning.effort override. Use 'none' to disable reasoning.",
    )
    parser.add_argument(
        "--reasoning-exclude",
        action="store_true",
        help="Set OpenRouter reasoning.exclude=true.",
    )
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0, help="Limit scenarios per model for smoke tests.")
    parser.add_argument("--overwrite", action="store_true", help="Do not skip completed request_ids.")
    parser.add_argument(
        "--no-system-prompt",
        action="store_true",
        help="Send exactly one user message and no system prompt; input CSV must use system_prompt_profile=no_system_baseline.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Write planned payload metadata only.")
    mode.add_argument("--execute", action="store_true", help="Send OpenRouter completion requests.")
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()

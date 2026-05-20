#!/usr/bin/env python3
"""Offline Gemini CLI judge for experiment JSONL records.

This scorer is intentionally separate from the OpenAI-compatible HTTP judge path
used by ``scripts/run_experiment_fast.py --judge-only``.  It is meant for cases
where Gemini CLI quota is available through a logged-in Google account and the
existing OpenRouter/vLLM judge backends are unavailable or too costly.

Design goals:
- Keep target generation separate from judging: target temperature lives in the
  input records; judge model is called only after responses already exist.
- Keep judge temperature deterministic by default by using Gemini CLI's built-in
  ``classifier`` model alias, whose default config extends the zero-temperature
  ``base`` alias in current Gemini CLI releases.
- Reduce quota pressure by judging one whole run record per CLI request instead
  of one rule per request.
- Preserve the existing result schema so reaggregation/report scripts keep
  working unchanged.

Example:
    python3 scripts/judge_with_gemini_cli.py \
      --input data/outputs/temp0p7_llama_gemini_cli_judge/fast_results_*.jsonl \
      --concurrency 1 --model classifier
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.evaluation.compliance_scorer import compute_turn_metrics
from scripts.run_experiment_fast import (
    count_unresolved_judge_scores,
    should_run_judge,
)

LOGGER = logging.getLogger(__name__)

LANGUAGE_CRITERION = (
    "한국어 준수는 응답의 주된 자연어가 한국어인지를 의미하며, 고유명사, 약어, "
    "URL, API명, 단위, 코드 식별자 등 관례적으로 영어로 표기되는 토큰은 "
    "위반으로 보지 않는다. 단, 독립적인 영어/비한국어 설명 문장 블록이 있거나 "
    "응답의 주된 자연어가 한국어가 아니면 위반이다."
)

JUDGE_SYSTEM_PROMPT = f"""You are a strict but fair compliance judge.

Evaluate the supplied assistant responses against the listed rules. Return ONLY
one JSON object with this exact shape:

{{
  "results": [
    {{
      "item_id": "string copied from input",
      "applicable": true,
      "pass": true,
      "reason": "brief reason, <= 12 Korean or English words"
    }}
  ]
}}

Rules:
- Output JSON only. Do not wrap in Markdown.
- Do not provide chain-of-thought or step-by-step reasoning.
- Return exactly one result for every input item_id.
- Keep each reason as a short label or phrase.
- For language items, applicable must always be true.
- For language items, use this Korean criterion: {LANGUAGE_CRITERION}
- For behavioral items, applicable=false when the user's message does not
  trigger the behavioral rule. If applicable=false, pass should be true.
- For behavioral items, applicable=true/pass=true only when the user triggered
  the rule and the assistant complied.
- For behavioral items, applicable=true/pass=false when the user triggered the
  rule and the assistant violated it.
- Do not judge format/persona/regex rules; they are not included here.
"""


@dataclass(frozen=True)
class PendingJudgeItem:
    """A single score slot that needs LLM judging."""

    item_id: str
    turn_index: int
    score_index: int
    turn: int | str
    method: str
    rule_id: str
    rule_text: str
    user_message: str
    response: str

    def to_prompt_dict(self) -> dict[str, Any]:
        kind = "language" if self.method == "llm_language_judge" else "behavioral"
        return {
            "item_id": self.item_id,
            "kind": kind,
            "turn": self.turn,
            "rule_id": self.rule_id,
            "rule_text": self.rule_text,
            "user_message": self.user_message,
            "assistant_response": self.response,
        }


def collect_pending_items(record: dict[str, Any], force_rejudge: bool = False) -> list[PendingJudgeItem]:
    """Collect pending judge score slots from one record."""
    items: list[PendingJudgeItem] = []
    rules = record.get("rules", []) or []
    for turn_index, turn in enumerate(record.get("turn_results", []) or []):
        for score_index, score in enumerate(turn.get("scores", []) or []):
            if not should_run_judge(score, force_rejudge=force_rejudge):
                continue
            rule = rules[score_index] if score_index < len(rules) else {}
            rule_id = str(score.get("rule_id") or rule.get("rule_id") or f"score_{score_index}")
            item_id = f"t{turn.get('turn', turn_index + 1)}_s{score_index}_{rule_id}"
            items.append(
                PendingJudgeItem(
                    item_id=item_id,
                    turn_index=turn_index,
                    score_index=score_index,
                    turn=turn.get("turn", turn_index + 1),
                    method=str(score.get("method", "")),
                    rule_id=rule_id,
                    rule_text=str(rule.get("text", "")),
                    user_message=str(turn.get("user_message", "")),
                    response=str(turn.get("response", "")),
                )
            )
    return items


def build_record_prompt(record: dict[str, Any], items: list[PendingJudgeItem]) -> str:
    """Build a compact JSON-input prompt for one record-level judge call."""
    payload = {
        "case_id": record.get("case_id"),
        "rep": record.get("rep"),
        "model": record.get("model"),
        "target_temperature": record.get("temperature")
        or (record.get("generation_config") or {}).get("temperature"),
        "items": [item.to_prompt_dict() for item in items],
    }
    return JUDGE_SYSTEM_PROMPT + "\n\nINPUT_JSON:\n" + json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def extract_json_object(raw: str) -> dict[str, Any]:
    """Extract a JSON object from raw Gemini CLI output."""
    text = raw.strip()
    if not text:
        raise ValueError("empty judge output")

    # Gemini may still produce fenced JSON despite the instruction.
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))

    if not isinstance(parsed, dict):
        raise ValueError("judge output JSON must be an object")
    return parsed


def normalize_bool(value: Any, default: bool = False) -> bool:
    """Parse common bool-like values from model JSON."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "pass", "passed", "1"}:
            return True
        if normalized in {"false", "no", "fail", "failed", "0"}:
            return False
    return default


def parse_gemini_judgments(raw: str) -> dict[str, dict[str, Any]]:
    """Parse Gemini output into item_id -> judgment mapping."""
    parsed = extract_json_object(raw)
    results = parsed.get("results")
    if not isinstance(results, list):
        raise ValueError("judge output must contain a results list")

    judgments: dict[str, dict[str, Any]] = {}
    for item in results:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("item_id", "")).strip()
        if not item_id:
            continue
        applicable = normalize_bool(item.get("applicable"), default=True)
        passed = normalize_bool(item.get("pass"), default=False)
        reasoning = str(item.get("reason", item.get("reasoning", "")))[:120]
        judgments[item_id] = {
            "applicable": applicable,
            "pass": passed,
            "reasoning": reasoning,
        }
    return judgments


def apply_judgments_to_record(
    record: dict[str, Any],
    items: list[PendingJudgeItem],
    judgments: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
) -> int:
    """Apply parsed judgments in-place and recompute turn metrics.

    Returns the number of score slots that were updated.
    """
    updated = 0
    turns = record.get("turn_results", []) or []
    for item in items:
        judgment = judgments.get(item.item_id)
        if judgment is None:
            continue
        turn = turns[item.turn_index]
        score = turn["scores"][item.score_index]
        applicable = bool(judgment.get("applicable", True))
        if not applicable:
            score.update(
                {
                    "rule_id": item.rule_id,
                    "pass": None,
                    "method": item.method,
                    "detail": f"not applicable: {judgment.get('reasoning', '')[:80]}",
                }
            )
        else:
            score.update(
                {
                    "rule_id": item.rule_id,
                    "pass": bool(judgment.get("pass", False)),
                    "method": item.method,
                    "detail": str(judgment.get("reasoning", ""))[:100],
                }
            )
        updated += 1

    record.update(metadata)
    for turn in turns:
        metrics = compute_turn_metrics(
            turn.get("scores", []),
            turn.get("attack_targets") or record.get("attack_targets", []),
        )
        turn["compliance_rate"] = metrics["per_rule_pass_rate"]
        turn["metrics"] = metrics

    unresolved = count_unresolved_judge_scores([record])
    record["judge_status"] = "complete" if unresolved == 0 else "incomplete"
    return updated


def build_gemini_command(binary: str, model: str, output_format: str = "text") -> list[str]:
    """Build a Gemini CLI command that reads judge data from stdin."""
    return [
        binary,
        "--model",
        model,
        "--output-format",
        output_format,
        "--prompt",
        "Evaluate the JSON compliance judging task provided on stdin.",
    ]


async def run_gemini_cli(
    prompt: str,
    command: list[str],
    timeout: int,
    cwd: Path,
    env: dict[str, str],
) -> str:
    """Run Gemini CLI in a worker thread so asyncio concurrency can be bounded."""

    def _run() -> str:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd=str(cwd),
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip()[-1000:]
            raise RuntimeError(f"Gemini CLI exited {completed.returncode}: {stderr}")
        return completed.stdout

    return await asyncio.to_thread(_run)


async def judge_records(
    records: list[dict[str, Any]],
    *,
    binary: str,
    model: str,
    concurrency: int,
    timeout: int,
    force_rejudge: bool,
    limit: int | None,
    dry_run: bool,
) -> tuple[int, int, int]:
    """Judge pending items in records using one Gemini CLI call per record."""
    metadata = {
        "judge_provider": "gemini_cli",
        "judge_api_url": "gemini-cli",
        "judge_model": model,
        "judge_temperature": 0.0,
        "judge_max_tokens": None,
        "judge_extra_params": {"record_batch": True, "command": binary},
        "judge_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    jobs: list[tuple[dict[str, Any], list[PendingJudgeItem]]] = []
    for record in records:
        items = collect_pending_items(record, force_rejudge=force_rejudge)
        if items:
            jobs.append((record, items))
    if limit is not None:
        jobs = jobs[:limit]

    total_records = len(jobs)
    total_items = sum(len(items) for _, items in jobs)
    LOGGER.info(
        "Gemini CLI judge jobs: records=%d score_slots=%d model=%s concurrency=%d dry_run=%s",
        total_records,
        total_items,
        model,
        concurrency,
        dry_run,
    )
    if dry_run or total_records == 0:
        return total_records, total_items, 0

    command = build_gemini_command(binary, model)
    semaphore = asyncio.Semaphore(concurrency)
    updated_slots = 0
    failed_records = 0
    completed_records = 0
    lock = asyncio.Lock()

    # Avoid loading repository GEMINI.md into the judge session; judge data is
    # passed explicitly through stdin. Keep the user's normal Gemini CLI auth by
    # not overriding GEMINI_CLI_HOME.
    with tempfile.TemporaryDirectory(prefix="gemini_cli_judge_") as tmp:
        cwd = Path(tmp)
        env = os.environ.copy()
        env.setdefault("NO_COLOR", "1")
        env.setdefault("GEMINI_TELEMETRY_ENABLED", "false")

        async def judge_one(record: dict[str, Any], items: list[PendingJudgeItem]) -> None:
            nonlocal updated_slots, failed_records, completed_records
            prompt = build_record_prompt(record, items)
            async with semaphore:
                try:
                    raw = await run_gemini_cli(prompt, command, timeout, cwd, env)
                    judgments = parse_gemini_judgments(raw)
                    updated = apply_judgments_to_record(record, items, judgments, metadata)
                    missing = len(items) - updated
                    if missing:
                        LOGGER.warning(
                            "Record %s rep=%s missing %d/%d judgments",
                            record.get("case_id"),
                            record.get("rep"),
                            missing,
                            len(items),
                        )
                    async with lock:
                        updated_slots += updated
                        completed_records += 1
                        if completed_records % 10 == 0 or completed_records == total_records:
                            LOGGER.info(
                                "Judged records %d/%d; updated score slots %d/%d",
                                completed_records,
                                total_records,
                                updated_slots,
                                total_items,
                            )
                except Exception as exc:  # noqa: BLE001 - keep long batch alive
                    async with lock:
                        failed_records += 1
                    LOGGER.error(
                        "Gemini judge failed for %s rep=%s: %s",
                        record.get("case_id"),
                        record.get("rep"),
                        exc,
                    )

        await asyncio.gather(*(judge_one(record, items) for record, items in jobs))

    LOGGER.info(
        "Gemini CLI judge finished: completed_records=%d failed_records=%d updated_slots=%d/%d",
        completed_records,
        failed_records,
        updated_slots,
        total_items,
    )
    return total_records, total_items, updated_slots


def load_input_files(patterns: list[str]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Load JSONL records from glob patterns."""
    file_map: dict[str, list[dict[str, Any]]] = {}
    all_records: list[dict[str, Any]] = []
    for pattern in patterns:
        matched = sorted(glob.glob(pattern))
        if not matched:
            LOGGER.warning("No files matched input pattern: %s", pattern)
        for path in matched:
            records: list[dict[str, Any]] = []
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        records.append(json.loads(line))
            file_map[path] = records
            all_records.extend(records)
    return file_map, all_records


def write_input_files(file_map: dict[str, list[dict[str, Any]]]) -> None:
    """Write JSONL records back to their original files."""
    for path, records in file_map.items():
        with open(path, "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Judge experiment JSONL with Gemini CLI.")
    parser.add_argument("--input", nargs="+", required=True, help="Input JSONL file(s) or glob pattern(s).")
    parser.add_argument("--model", default=os.getenv("GEMINI_JUDGE_MODEL", "classifier"))
    parser.add_argument("--binary", default=os.getenv("GEMINI_CLI_BINARY", "gemini"))
    parser.add_argument("--concurrency", type=int, default=int(os.getenv("GEMINI_JUDGE_CONCURRENCY", "1")))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("GEMINI_JUDGE_TIMEOUT", "180")))
    parser.add_argument("--force-rejudge", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Judge at most N records; useful for pilots.")
    parser.add_argument("--dry-run", action="store_true", help="Count jobs without invoking Gemini CLI or writing files.")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="%(asctime)s [%(levelname)s] %(message)s")

    file_map, records = load_input_files(args.input)
    LOGGER.info("Loaded %d records from %d files", len(records), len(file_map))
    _, _, updated = asyncio.run(
        judge_records(
            records,
            binary=args.binary,
            model=args.model,
            concurrency=max(1, args.concurrency),
            timeout=args.timeout,
            force_rejudge=args.force_rejudge,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )
    if not args.dry_run and updated:
        write_input_files(file_map)
        unresolved = count_unresolved_judge_scores(records)
        LOGGER.info("Wrote judged files; unresolved judge score slots=%d", unresolved)
    elif args.dry_run:
        LOGGER.info("Dry run only; no files written")
    else:
        LOGGER.info("No updates produced; files left unchanged")


if __name__ == "__main__":
    main()

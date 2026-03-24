"""OpenRouter API client for experiment case inference.

Processes experiment cases: builds message sequences from system_prompt +
intermediate_turns + probe_turn, sends to target model, collects responses.

For 'user_only' intermediate turns, generates assistant responses interactively.
For 'full' intermediate turns, injects pre-existing conversation directly.

Usage:
    python -m src.models.open_router_request --input data/processed/compressed_cases/sliding_window_3/experiment_cases.jsonl --output data/outputs/
"""

import argparse
import asyncio
import json
import logging
import os
import time
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "qwen/qwen3.5-9b"
MAX_RETRIES = 3
BACKOFF_BASE = 2


async def run_single_case(
    session: aiohttp.ClientSession,
    headers: dict,
    case: dict,
    model: str,
) -> dict:
    """Run inference for a single experiment case.

    Supports both v2 (rendered_user_message) and legacy (probe_turn) formats.

    Args:
        session: aiohttp session.
        headers: Request headers with auth.
        case: Experiment case dict.
        model: Model identifier.

    Returns:
        Output record dict.
    """
    start_time = time.monotonic()

    messages: list[dict] = []

    # Add system prompt if present
    system_prompt = case.get("system_prompt", "")
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    turns_type = case.get("intermediate_turns_type", "none")

    if turns_type == "full":
        # Case 3 (Alignment Tax): inject full intermediate turns + target question
        intermediate = case.get("intermediate_turns", [])
        messages.extend(intermediate)
        target_q = case.get("target_question", "")
        if target_q:
            messages.append({"role": "user", "content": target_q})
    elif "rendered_user_message" in case:
        # Baseline / Normal / MC-embedded: single rendered user message
        messages.append({"role": "user", "content": case["rendered_user_message"]})
    else:
        # Legacy format: intermediate_turns + probe_turn
        intermediate = case.get("intermediate_turns", [])
        if turns_type == "full":
            messages.extend(intermediate)
        elif turns_type == "user_only":
            for turn in intermediate:
                messages.append(turn)
                if turn["role"] == "user":
                    assistant_resp = await _call_api(session, headers, messages, model)
                    messages.append({"role": "assistant", "content": assistant_resp})
        messages.append(case["probe_turn"])

    # Get model response
    probe_response = await _call_api(session, headers, messages, model)
    elapsed_ms = (time.monotonic() - start_time) * 1000

    # Token count from case metadata or approximate
    total_tokens = case.get("token_counts", {}).get("total_context_tokens", 0)
    if not total_tokens:
        total_tokens = sum(len(m.get("content", "").split()) for m in messages)

    # Build output record
    record = {
        "case_id": case["case_id"],
        "original_case_id": case.get("original_case_id", case["case_id"]),
        "model": model,
        "condition": case["condition"],
        "response": probe_response,
        "system_prompt": system_prompt,
        "probe_id": case.get("probe_id", ""),
        "target_rule": case.get("target_rule", 0),
        "scoring": case.get("scoring", {}),
        "latency_ms": round(elapsed_ms, 2),
        "tokens_used": total_tokens,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }

    # Include compression metadata if present
    if "compression_metadata" in case:
        record["compression_metadata"] = case["compression_metadata"]

    # Include intermediate_turns for AT cases (needed by judge)
    if case.get("intermediate_turns_type") == "full":
        record["intermediate_turns"] = case.get("intermediate_turns", [])

    return record


async def _call_api(
    session: aiohttp.ClientSession,
    headers: dict,
    messages: list[dict],
    model: str,
) -> str:
    """Make a single API call with retry logic.

    Args:
        session: aiohttp session.
        headers: Auth headers.
        messages: Message list.
        model: Model identifier.

    Returns:
        Model response content string.
    """
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.0,
        "reasoning": {"effort": "none"},
    }

    for attempt in range(MAX_RETRIES):
        try:
            async with session.post(API_URL, headers=headers, json=payload) as resp:
                if resp.status == 429:
                    wait = BACKOFF_BASE ** attempt * 10
                    logger.warning("Rate limited, waiting %ds (attempt %d)", wait, attempt + 1)
                    await asyncio.sleep(wait)
                    continue

                result = await resp.json()

                if "choices" in result and result["choices"]:
                    return result["choices"][0]["message"]["content"]

                error_msg = result.get("error", {}).get("message", str(result))
                logger.warning("API error: %s", error_msg)

                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BACKOFF_BASE ** attempt)

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning("Request failed (attempt %d): %s: %s", attempt + 1, type(e).__name__, e)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(BACKOFF_BASE ** attempt)

    return "[ERROR] All retries failed"


async def run_inference(
    input_path: str,
    output_dir: str,
    model: str = DEFAULT_MODEL,
    concurrency: int = 5,
    checkpoint: bool = True,
) -> list[dict]:
    """Run inference on all cases from an input file.

    Args:
        input_path: Path to experiment_cases.jsonl.
        output_dir: Directory for output files.
        model: Model identifier.
        concurrency: Max concurrent API sessions.
        checkpoint: If True, skip already-processed case_ids.

    Returns:
        List of output records.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        logger.error("OPENROUTER_API_KEY not set")
        return []

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "http://localhost",
        "Content-Type": "application/json",
    }

    # Load cases
    cases: list[dict] = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    logger.info("Loaded %d cases from %s", len(cases), input_path)

    # Determine output path
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Derive variant name from input path
    input_p = Path(input_path)
    variant_name = input_p.parent.name if input_p.parent.name != "processed" else "baseline"
    model_slug = model.replace("/", "_")
    result_file = output_path / model_slug / variant_name / "results.jsonl"
    result_file.parent.mkdir(parents=True, exist_ok=True)

    # Load checkpoint (already processed case_ids)
    processed_ids: set[str] = set()
    if checkpoint and result_file.exists():
        with open(result_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    processed_ids.add(rec["case_id"])
        logger.info("Checkpoint: %d cases already processed", len(processed_ids))

    remaining = [c for c in cases if c["case_id"] not in processed_ids]
    logger.info("Running inference on %d remaining cases", len(remaining))

    if not remaining:
        logger.info("All cases already processed")
        return []

    results: list[dict] = []
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_run(case: dict) -> dict:
        async with semaphore:
            return await run_single_case(session, headers, case, model)

    timeout = aiohttp.ClientTimeout(total=180, connect=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = [bounded_run(case) for case in remaining]

        # Process and write results as they complete
        with open(result_file, "a", encoding="utf-8") as out_f:
            for i, coro in enumerate(asyncio.as_completed(tasks)):
                record = await coro
                results.append(record)
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                out_f.flush()

                if (i + 1) % 10 == 0 or i + 1 == len(remaining):
                    logger.info("Progress: %d/%d cases", i + 1, len(remaining))

    logger.info("Inference complete: %d records written to %s", len(results), result_file)
    return results


async def run_all_variants(
    compressed_dir: str,
    output_dir: str,
    model: str = DEFAULT_MODEL,
    concurrency: int = 5,
) -> dict[str, list[dict]]:
    """Run inference on all compression variants.

    Args:
        compressed_dir: Directory containing variant subdirectories.
        output_dir: Output directory for results.
        model: Model identifier.
        concurrency: Max concurrent sessions.

    Returns:
        Dict mapping variant_name to list of output records.
    """
    compressed_path = Path(compressed_dir)
    all_results: dict[str, list[dict]] = {}

    # Find all variant directories
    variant_dirs = sorted(
        d for d in compressed_path.iterdir()
        if d.is_dir() and (d / "experiment_cases.jsonl").exists()
    )

    logger.info("Found %d variants in %s", len(variant_dirs), compressed_dir)

    for variant_dir in variant_dirs:
        input_file = variant_dir / "experiment_cases.jsonl"
        logger.info("Processing variant: %s", variant_dir.name)

        results = await run_inference(
            str(input_file), output_dir, model, concurrency
        )
        all_results[variant_dir.name] = results

    total = sum(len(v) for v in all_results.values())
    logger.info("All variants complete: %d total records", total)
    return all_results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Run inference on experiment cases.")
    parser.add_argument(
        "--input", type=str,
        help="Path to a single experiment_cases.jsonl file.",
    )
    parser.add_argument(
        "--compressed-dir", type=str,
        default="data/processed/compressed_cases",
        help="Directory with compression variant subdirectories.",
    )
    parser.add_argument(
        "--output", type=str, default="data/outputs",
        help="Output directory for results.",
    )
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL,
        help="Model identifier for OpenRouter.",
    )
    parser.add_argument(
        "--concurrency", type=int, default=5,
        help="Max concurrent API calls.",
    )
    args = parser.parse_args()

    if args.input:
        asyncio.run(run_inference(args.input, args.output, args.model, args.concurrency))
    else:
        asyncio.run(run_all_variants(args.compressed_dir, args.output, args.model, args.concurrency))

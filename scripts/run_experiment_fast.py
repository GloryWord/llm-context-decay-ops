"""Fast experiment runner: auto-scoring only, deferred LLM-judge, case-level concurrency.

Phase 1: Run inference + auto-scoring (no judge calls) — ~10x faster
Phase 2: Batch LLM-judge for behavioral rules (separate pass)

Usage:
    # Fast inference (no judge)
    python3 scripts/run_experiment_fast.py --models vllm --reps 5 --concurrency 6

    # Temperature sweep inference (judge is still deferred)
    python3 scripts/run_experiment_fast.py --models vllm --temperature 0.7 \
        --output-dir data/outputs/temp_sweep_t0p7

    # After inference, run batch judge. Select judge backend via env:
    #   JUDGE_PROVIDER=vllm JUDGE_API_URL=http://host:port/v1/chat/completions
    #   JUDGE_MODEL_NAME=<local-model-name>
    python3 scripts/run_experiment_fast.py --judge-only \
        --input data/outputs/temp_sweep_t0p7/fast_results_*.jsonl

    # Re-score an already judged copy with a different judge model.
    python3 scripts/run_experiment_fast.py --judge-only --force-rejudge \
        --input data/outputs/temp0_gemma_judge/fast_results_*.jsonl
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.evaluation.compliance_scorer import (
    compute_turn_metrics,
    score_behavioral_async,
    score_language_async,
    score_rules,
)
from src.evaluation.judge_config import (
    build_judge_headers,
    judge_metadata,
    resolve_judge_config,
)
from src.utils.http_headers import build_json_headers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================
# Model configurations
# ============================================================

MODEL_CONFIGS: dict[str, dict] = {
    "vllm": {
        "api_url": os.getenv("VLLM_API_URL", "http://210.179.28.26:18000/v1/chat/completions"),
        "model_name": os.getenv("EVAL_MODEL_NAME", "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4"),
        "api_key": os.getenv("VLLM_API_KEY", ""),
        "extra_params": {},
    },
    "deepseek-r1": {
        "api_url": "https://openrouter.ai/api/v1/chat/completions",
        "model_name": "deepseek/deepseek-r1",
        "api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "extra_params": {},
    },
    "openrouter-llama-3.1-8b": {
        "api_url": os.getenv(
            "OPENROUTER_API_URL",
            "https://openrouter.ai/api/v1/chat/completions",
        ),
        "model_name": os.getenv(
            "OPENROUTER_TARGET_MODEL_NAME",
            "meta-llama/llama-3.1-8b-instruct",
        ),
        "api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "extra_params": {},
    },
}

CASES_FILE = ROOT / "data" / "processed" / "experiment_cases_full.jsonl"
OUTPUT_DIR = ROOT / "data" / "outputs" / "main_experiment"


def temperature_tag(temperature: float) -> str:
    """Return a filesystem/checkpoint-safe tag for a generation temperature."""
    value = f"{temperature:.3f}".rstrip("0").rstrip(".")
    return "temp" + value.replace("-", "m").replace(".", "p")


def record_temperature(record: dict) -> float:
    """Read generation temperature from a result record, defaulting old rows to 0.0."""
    if "temperature" in record:
        return float(record["temperature"])
    generation_config = record.get("generation_config", {})
    if "temperature" in generation_config:
        return float(generation_config["temperature"])
    return 0.0


def run_id_for(case_id: str, rep: int, model_name: str, temperature: float) -> str:
    """Build a checkpoint key that keeps temperature sweeps separate."""
    return f"{case_id}_{rep}_{model_name}_{temperature_tag(temperature)}"


def case_metadata(case: dict) -> dict:
    """Return experiment-design metadata that should survive result serialization."""
    return {
        "design_version": case.get("design_version", ""),
        "research_question": case.get("research_question", ""),
        "system_prompt_profile": case.get("system_prompt_profile", ""),
        "q2_profile_caveat": case.get("q2_profile_caveat", ""),
        "condition": case.get("condition"),
        "rule_count": case["rule_count"],
        "turn_count": case["turn_count"],
        "target_rule_id": case.get("target_rule_id"),
        "target_rule_category": case.get("target_rule_category"),
        "attack_intensity": case.get("attack_intensity", ""),
        "attack_scope": case.get("attack_scope"),
        "attack_targets": case.get("attack_targets", []),
        "attack_mode": case.get("attack_mode", ""),
        "attack_order_variant": case.get("attack_order_variant", ""),
        "attack_order": case.get("attack_order", []),
        "order_average_group_id": case.get("order_average_group_id", ""),
        "sampled_variant_id": case.get("sampled_variant_id", ""),
        "possible_variant_id": case.get("possible_variant_id", ""),
        "sampling_seed": case.get("sampling_seed"),
        "samples_per_rule_count": case.get("samples_per_rule_count"),
        "possible_combination_count": case.get("possible_combination_count"),
        "sampled_combination_count": case.get("sampled_combination_count"),
        "active_rule_ids": case.get("active_rule_ids", case.get("rule_set_variant", [])),
        "filler_rule_ids": case.get("filler_rule_ids", []),
        "filler_category_composition": case.get("filler_category_composition", {}),
        "active_category_composition": case.get("active_category_composition", {}),
        "rule_set_variant": case.get("rule_set_variant", []),
        "single_turn_attack_policy": case.get("single_turn_attack_policy", ""),
        "schedule": case.get("schedule", []),
        "source_attack_prompt_file": case.get("source_attack_prompt_file", ""),
        "source_scenario_ids": case.get("source_scenario_ids", []),
    }


def has_unresolved_judge_score(score: dict) -> bool:
    """Return True when a judge-based score still needs a valid judge result."""
    if score.get("method") not in {"llm_judge", "llm_language_judge"}:
        return False
    if score.get("pass") is not None:
        return False
    detail = str(score.get("detail", "")).lower()
    return not detail.startswith("not applicable")


def count_unresolved_judge_scores(records: list[dict]) -> int:
    """Count unresolved judge-based scores after batch judging."""
    return sum(
        1
        for record in records
        for turn in record.get("turn_results", [])
        for score in turn.get("scores", [])
        if has_unresolved_judge_score(score)
    )


def should_run_judge(score: dict, force_rejudge: bool = False) -> bool:
    """Return True when a score should be sent to the configured judge."""
    if score.get("method") not in {"llm_judge", "llm_language_judge"}:
        return False
    if force_rejudge:
        return True
    return has_unresolved_judge_score(score)


def judge_score_key(record: dict, turn: dict, score_index: int, score: dict) -> dict:
    """Build a stable key for one judge score slot.

    The key is intentionally independent of row order so that sidecar judge
    checkpoints can be replayed after an interrupted judge-only run.
    """
    return {
        "case_id": str(record.get("case_id", "")),
        "rep": int(record.get("rep", 0)),
        "model": str(record.get("model", "")),
        "temperature": record_temperature(record),
        "turn": turn.get("turn"),
        "score_index": score_index,
        "rule_id": str(score.get("rule_id", "")),
    }


def judge_score_key_tuple(key: dict) -> tuple:
    """Convert a judge score key dict into a hashable tuple."""
    return (
        str(key.get("case_id", "")),
        int(key.get("rep", 0)),
        str(key.get("model", "")),
        float(key.get("temperature", 0.0)),
        key.get("turn"),
        int(key.get("score_index", -1)),
        str(key.get("rule_id", "")),
    )


def judge_checkpoint_path(result_path: str | Path) -> Path:
    """Return the sidecar path used for incremental judge checkpoints."""
    path = Path(result_path)
    return path.with_name(f"{path.name}.judge_checkpoint.jsonl")


def refresh_judge_records(records: list[dict], metadata: dict) -> int:
    """Refresh record-level judge metadata/status after score changes."""
    unresolved_after = count_unresolved_judge_scores(records)
    for record in records:
        record.update(metadata)
        for turn in record.get("turn_results", []):
            metrics = compute_turn_metrics(
                turn["scores"],
                turn.get("attack_targets") or record.get("attack_targets", []),
            )
            turn["compliance_rate"] = metrics["per_rule_pass_rate"]
            turn["metrics"] = metrics
        record_unresolved = count_unresolved_judge_scores([record])
        record["judge_status"] = "complete" if record_unresolved == 0 else "incomplete"
    return unresolved_after


def write_result_files(file_map: dict[str, list[dict]]) -> None:
    """Atomically rewrite result JSONL files from in-memory records."""
    for path_text, file_records in file_map.items():
        path = Path(path_text)
        tmp_path = path.with_name(f"{path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as handle:
            for record in file_records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        os.replace(tmp_path, path)


def apply_judge_checkpoints(
    file_map: dict[str, list[dict]],
    metadata: dict,
    force_rejudge: bool = False,
) -> int:
    """Replay sidecar judge checkpoints into loaded records.

    Sidecars let an interrupted judge-only run resume from the last completed
    score slot instead of losing all in-memory progress.
    """
    if force_rejudge:
        return 0

    applied = 0
    for path_text, file_records in file_map.items():
        checkpoint = judge_checkpoint_path(path_text)
        if not checkpoint.exists():
            continue

        slot_index: dict[tuple, tuple[dict, dict, int]] = {}
        for record in file_records:
            for turn in record.get("turn_results", []):
                for index, score in enumerate(turn.get("scores", [])):
                    if score.get("method") in {"llm_judge", "llm_language_judge"}:
                        key = judge_score_key(record, turn, index, score)
                        slot_index[judge_score_key_tuple(key)] = (record, turn, index)

        latest_by_key: dict[tuple, dict] = {}
        with open(checkpoint, "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                entry = json.loads(line)
                key = judge_score_key_tuple(entry.get("key", {}))
                latest_by_key[key] = entry

        for key, entry in latest_by_key.items():
            if key not in slot_index:
                continue
            record, turn, index = slot_index[key]
            score = entry.get("score")
            if isinstance(score, dict):
                turn["scores"][index] = score
                applied += 1

    if applied:
        refresh_judge_records(
            [record for file_records in file_map.values() for record in file_records],
            metadata,
        )
    return applied


def append_judge_checkpoint(
    result_path: str | Path,
    record: dict,
    turn: dict,
    score_index: int,
    score: dict,
    metadata: dict,
) -> None:
    """Append one completed judge score to the sidecar checkpoint file."""
    checkpoint = judge_checkpoint_path(result_path)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "key": judge_score_key(record, turn, score_index, score),
        "score": score,
        "judge_metadata": metadata,
    }
    with open(checkpoint, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


async def call_model_with_metadata(
    session: aiohttp.ClientSession,
    model_cfg: dict,
    messages: list[dict],
    temperature: float = 0.0,
) -> tuple[str, dict]:
    """Call target model API with retry and preserve response metadata."""
    headers = build_json_headers(model_cfg["api_url"], model_cfg["api_key"])
    payload = {
        "model": model_cfg["model_name"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 512,
        **model_cfg.get("extra_params", {}),
    }

    for attempt in range(3):
        try:
            async with session.post(model_cfg["api_url"], headers=headers, json=payload) as resp:
                if resp.status == 429:
                    await asyncio.sleep(2 ** attempt * 5)
                    continue
                result = await resp.json()
                if "choices" in result and result["choices"]:
                    choice = result["choices"][0]
                    metadata = {
                        "finish_reason": choice.get("finish_reason"),
                        "usage": result.get("usage"),
                        "model": result.get("model"),
                        "id": result.get("id"),
                        "created": result.get("created"),
                    }
                    return choice["message"]["content"], metadata
                logger.warning("API error: %s", result.get("error", {}).get("message", str(result))[:100])
                await asyncio.sleep(2 ** attempt)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning("Request failed (attempt %d): %s", attempt + 1, e)
            await asyncio.sleep(2 ** attempt)
    return "[ERROR] All retries failed", {"error": "all_retries_failed"}


async def call_model(
    session: aiohttp.ClientSession,
    model_cfg: dict,
    messages: list[dict],
    temperature: float = 0.0,
) -> str:
    """Call target model API with retry."""
    content, _metadata = await call_model_with_metadata(
        session,
        model_cfg,
        messages,
        temperature,
    )
    return content


async def run_single_case_fast(
    session: aiohttp.ClientSession,
    model_cfg: dict,
    case: dict,
    rep: int,
    temperature: float = 0.0,
) -> dict:
    """Run case with auto-scoring only (no judge). ~10x faster."""
    messages: list[dict] = [{"role": "system", "content": case["system_prompt"]}]
    turn_results: list[dict] = []

    for turn_info in case["conversation_template"]:
        user_content = turn_info["content"]
        messages.append({"role": "user", "content": user_content})

        response, response_metadata = await call_model_with_metadata(
            session,
            model_cfg,
            messages,
            temperature,
        )
        if response.startswith("[ERROR]"):
            raise RuntimeError(
                f"model call failed for {case.get('case_id')} turn {turn_info['turn']}"
            )
        messages.append({"role": "assistant", "content": response})

        attack_targets = turn_info.get("attack_targets", [])
        attack_mode = turn_info.get("attack_mode", case.get("attack_mode", ""))

        # Auto-scoring only — judge-based rules stay as pending (None)
        scores = score_rules(response, case["rules"])
        metrics = compute_turn_metrics(scores, attack_targets)
        compliance = metrics["per_rule_pass_rate"]

        turn_results.append({
            "turn": turn_info["turn"],
            "user_message": user_content,
            "attack_targets": attack_targets,
            "attack_mode": attack_mode,
            "response": response,
            "scores": scores,
            "compliance_rate": compliance,
            "metrics": metrics,
            "response_length": len(response),
            "target_finish_reason": response_metadata.get("finish_reason"),
            "target_usage": response_metadata.get("usage"),
            "target_response_metadata": response_metadata,
        })

    return {
        "case_id": case["case_id"],
        "rep": rep,
        "model": model_cfg["model_name"],
        "temperature": temperature,
        "generation_config": {
            "temperature": temperature,
            "max_tokens": 512,
        },
        **case_metadata(case),
        "rules": case["rules"],
        "turn_results": turn_results,
        "judge_status": "pending",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def load_checkpoint(output_path: Path) -> set[str]:
    """Load completed run IDs from checkpoint file."""
    completed: set[str] = set()
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    run_id = run_id_for(
                        str(rec["case_id"]),
                        int(rec["rep"]),
                        str(rec["model"]),
                        record_temperature(rec),
                    )
                    completed.add(run_id)
    return completed


async def run_experiment_fast(
    models: list[str],
    reps: int = 5,
    concurrency: int = 6,
    dry_run: bool = False,
    cases_file: str | None = None,
    output_dir: str | None = None,
    temperature: float = 0.0,
) -> None:
    """Run experiment with case-level concurrency, no judge calls."""
    cases: list[dict] = []
    cases_path = Path(cases_file) if cases_file else CASES_FILE
    with open(cases_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))

    if dry_run:
        cases = cases[:10]
        reps = 1

    total = len(cases) * reps * len(models)
    logger.info(
        "Fast experiment: %d cases × %d reps × %d models = %d runs "
        "(concurrency=%d, target_temperature=%.3f)",
        len(cases), reps, len(models), total, concurrency, temperature,
    )

    resolved_output_dir = Path(output_dir) if output_dir else OUTPUT_DIR
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    for model_key in models:
        model_cfg = MODEL_CONFIGS[model_key]
        model_slug = model_cfg["model_name"].replace("/", "_")
        output_suffix = "" if temperature == 0.0 else f"_{temperature_tag(temperature)}"
        output_path = resolved_output_dir / f"fast_results_{model_slug}{output_suffix}.jsonl"

        completed = load_checkpoint(output_path)
        logger.info("Model %s: %d already completed", model_key, len(completed))

        # Build work queue
        work: list[tuple[dict, int]] = []
        for rep in range(reps):
            for case in cases:
                run_id = run_id_for(
                    str(case["case_id"]),
                    rep,
                    str(model_cfg["model_name"]),
                    temperature,
                )
                if run_id not in completed:
                    work.append((case, rep))

        logger.info("Remaining: %d runs", len(work))
        if not work:
            continue

        semaphore = asyncio.Semaphore(concurrency)
        timeout = aiohttp.ClientTimeout(total=120, connect=15)
        done_count = 0
        out_lock = asyncio.Lock()

        async with aiohttp.ClientSession(timeout=timeout) as session:
            failed_count = 0

            async def bounded_run(case_arg: dict, rep_arg: int) -> None:
                nonlocal done_count, failed_count
                async with semaphore:
                    try:
                        result = await run_single_case_fast(
                            session, model_cfg, case_arg, rep_arg, temperature
                        )
                    except Exception as exc:
                        failed_count += 1
                        logger.error(
                            "FAILED %s rep=%d: %s",
                            case_arg.get("case_id"),
                            rep_arg,
                            exc,
                        )
                        return

                async with out_lock:
                    with open(output_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(result, ensure_ascii=False) + "\n")
                    done_count += 1
                    if done_count % 20 == 0 or done_count == len(work):
                        final_c = result["turn_results"][-1]["compliance_rate"] if result["turn_results"] else 0
                        logger.info("[%d/%d] %s rep=%d → %.0f%%",
                                    done_count, len(work), case_arg["case_id"], rep_arg, final_c * 100)

            tasks = [bounded_run(c, r) for c, r in work]
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Model %s done: %d runs, %d failed", model_key, done_count, failed_count)


# ============================================================
# Phase 2: Batch judge
# ============================================================

async def batch_judge(
    input_patterns: list[str],
    concurrency: int = 6,
    force_rejudge: bool = False,
    checkpoint_every: int = 1000,
) -> None:
    """Post-process: score all pending judge-based rules via LLM-judge."""
    import glob

    judge_config = resolve_judge_config()
    judge_headers = build_judge_headers(judge_config)
    metadata = judge_metadata(judge_config)
    logger.info(
        "Judge backend: provider=%s model=%s url=%s temp=%.1f",
        metadata["judge_provider"],
        metadata["judge_model"],
        metadata["judge_api_url"],
        metadata["judge_temperature"],
    )

    records: list[dict] = []
    file_map: dict[str, list[dict]] = {}
    record_path_by_id: dict[int, str] = {}

    for pattern in input_patterns:
        for path in sorted(glob.glob(pattern)):
            file_records = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        file_records.append(record)
                        record_path_by_id[id(record)] = path
            file_map[path] = file_records
            records.extend(file_records)

    restored = apply_judge_checkpoints(file_map, metadata, force_rejudge=force_rejudge)
    if restored:
        write_result_files(file_map)
        logger.info("Restored %d judge score checkpoints before resume", restored)

    # Count judge calls
    judge_call_count = 0
    for r in records:
        for t in r.get("turn_results", []):
            for s in t.get("scores", []):
                if should_run_judge(s, force_rejudge):
                    judge_call_count += 1

    logger.info(
        "Total records: %d, judge calls: %d (force_rejudge=%s)",
        len(records),
        judge_call_count,
        force_rejudge,
    )
    if judge_call_count == 0:
        logger.info("No judge calls to run")
        return

    semaphore = asyncio.Semaphore(concurrency)
    timeout = aiohttp.ClientTimeout(total=60, connect=15)
    judged_count = 0
    checkpoint_lock = asyncio.Lock()

    async def write_checkpoint(reason: str) -> None:
        unresolved = refresh_judge_records(records, metadata)
        write_result_files(file_map)
        logger.info(
            "Judge checkpoint (%s): judged %d/%d, unresolved judge scores=%d",
            reason,
            judged_count,
            judge_call_count,
            unresolved,
        )

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async def judge_one(r: dict, t: dict, i: int, rule: dict) -> None:
            nonlocal judged_count
            async with semaphore:
                if t["scores"][i].get("method") == "llm_language_judge":
                    result = await score_language_async(
                        session,
                        judge_headers,
                        t["response"],
                        rule,
                        t["user_message"],
                        judge_config,
                    )
                else:
                    result = await score_behavioral_async(
                        session,
                        judge_headers,
                        t["response"],
                        rule,
                        t["user_message"],
                        judge_config,
                    )
                t["scores"][i] = result
                append_judge_checkpoint(
                    record_path_by_id[id(r)],
                    r,
                    t,
                    i,
                    result,
                    metadata,
                )
                judged_count += 1
                if judged_count % 50 == 0:
                    logger.info("Judged %d/%d", judged_count, judge_call_count)
                if checkpoint_every > 0 and judged_count % checkpoint_every == 0:
                    async with checkpoint_lock:
                        await write_checkpoint(f"every_{checkpoint_every}")

        tasks = []
        for r in records:
            rules = r.get("rules", [])
            for t in r.get("turn_results", []):
                for i, s in enumerate(t.get("scores", [])):
                    if should_run_judge(s, force_rejudge):
                        rule = rules[i] if i < len(rules) else {"rule_id": s["rule_id"], "text": ""}
                        tasks.append(judge_one(r, t, i, rule))

        await asyncio.gather(*tasks, return_exceptions=True)

    # Recompute compliance and write back
    unresolved_after = refresh_judge_records(records, metadata)
    write_result_files(file_map)

    logger.info(
        "Batch judge complete: %d calls, unresolved judge scores after pass: %d",
        judged_count,
        unresolved_after,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fast experiment runner.")
    parser.add_argument("--models", nargs="+", default=["vllm"], choices=list(MODEL_CONFIGS.keys()))
    parser.add_argument("--reps", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cases-file", default=None, help="Case JSONL file to run.")
    parser.add_argument("--output-dir", default=None, help="Directory for result JSONL files.")
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Target model generation temperature. Judge temperature remains fixed at 0.0.",
    )
    parser.add_argument("--judge-only", action="store_true", help="Run batch judge on existing results.")
    parser.add_argument("--input", nargs="+", default=None, help="Input patterns for --judge-only.")
    parser.add_argument(
        "--force-rejudge",
        action="store_true",
        help="In --judge-only mode, re-score all llm_judge/llm_language_judge entries instead of only pending scores.",
    )
    parser.add_argument(
        "--judge-checkpoint-every",
        type=int,
        default=int(os.getenv("JUDGE_CHECKPOINT_EVERY", "1000")),
        help=(
            "In --judge-only mode, atomically rewrite result JSONL after this "
            "many judge calls. A sidecar *.judge_checkpoint.jsonl is still "
            "appended after every score for interruption-safe resume. Use 0 "
            "to disable periodic full rewrites."
        ),
    )
    args = parser.parse_args()

    if args.judge_only:
        patterns = args.input or [str(OUTPUT_DIR / "fast_results_*.jsonl")]
        asyncio.run(
            batch_judge(
                patterns,
                args.concurrency,
                args.force_rejudge,
                args.judge_checkpoint_every,
            )
        )
    else:
        asyncio.run(run_experiment_fast(
            args.models,
            args.reps,
            args.concurrency,
            args.dry_run,
            args.cases_file,
            args.output_dir,
            args.temperature,
        ))


if __name__ == "__main__":
    main()

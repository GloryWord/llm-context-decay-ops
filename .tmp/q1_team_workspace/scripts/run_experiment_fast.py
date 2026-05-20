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
        "research_question": case.get("research_question", ""),
        "condition": case.get("condition"),
        "rule_count": case["rule_count"],
        "turn_count": case["turn_count"],
        "target_rule_id": case.get("target_rule_id"),
        "target_rule_category": case.get("target_rule_category"),
        "attack_intensity": case.get("attack_intensity", ""),
        "attack_scope": case.get("attack_scope"),
        "attack_targets": case.get("attack_targets", []),
        "attack_mode": case.get("attack_mode", ""),
        "rule_set_variant": case.get("rule_set_variant", []),
        "schedule": case.get("schedule", []),
        "source_attack_prompt_file": case.get("source_attack_prompt_file", ""),
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
    return score.get("pass") is None and "pending" in str(score.get("detail", ""))


async def call_model(
    session: aiohttp.ClientSession,
    model_cfg: dict,
    messages: list[dict],
    temperature: float = 0.0,
) -> str:
    """Call target model API with retry."""
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
                    return result["choices"][0]["message"]["content"]
                logger.warning("API error: %s", result.get("error", {}).get("message", str(result))[:100])
                await asyncio.sleep(2 ** attempt)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning("Request failed (attempt %d): %s", attempt + 1, e)
            await asyncio.sleep(2 ** attempt)
    return "[ERROR] All retries failed"


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

        response = await call_model(session, model_cfg, messages, temperature)
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

    for pattern in input_patterns:
        for path in sorted(glob.glob(pattern)):
            file_records = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        file_records.append(json.loads(line))
            file_map[path] = file_records
            records.extend(file_records)

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
                judged_count += 1
                if judged_count % 50 == 0:
                    logger.info("Judged %d/%d", judged_count, judge_call_count)

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
    unresolved_after = count_unresolved_judge_scores(records)
    for r in records:
        r.update(metadata)
        for t in r.get("turn_results", []):
            metrics = compute_turn_metrics(
                t["scores"],
                t.get("attack_targets") or r.get("attack_targets", []),
            )
            t["compliance_rate"] = metrics["per_rule_pass_rate"]
            t["metrics"] = metrics
        record_unresolved = count_unresolved_judge_scores([r])
        r["judge_status"] = "complete" if record_unresolved == 0 else "incomplete"

    for path, file_records in file_map.items():
        with open(path, "w", encoding="utf-8") as f:
            for r in file_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

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
    args = parser.parse_args()

    if args.judge_only:
        patterns = args.input or [str(OUTPUT_DIR / "fast_results_*.jsonl")]
        asyncio.run(batch_judge(patterns, args.concurrency, args.force_rejudge))
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

"""Main experiment runner: multi-turn compliance decay measurement.

Runs experiment cases through target models, scoring each turn's response
against all active guardrail rules. Supports:
- 5 repetitions per case (--reps)
- Multiple models (--models): vllm (Llama 3.1 8B), deepseek-r1
- Per-turn auto-scoring + async LLM-judge for behavioral rules
- Checkpoint/resume (skips completed case+rep+model combos)

Usage:
    # Dry-run (5 cases)
    python scripts/run_experiment.py --dry-run

    # Full experiment
    python scripts/run_experiment.py --reps 5 --models vllm deepseek-r1

    # Resume interrupted run
    python scripts/run_experiment.py --reps 5 --models vllm deepseek-r1
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
    compute_compliance_rate,
    score_behavioral_async,
    score_rules,
)

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
        "api_url": os.getenv(
            "VLLM_API_URL", "http://210.179.28.26:18000/v1/chat/completions"
        ),
        "model_name": os.getenv(
            "EVAL_MODEL_NAME",
            "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4",
        ),
        "api_key": os.getenv("OPENROUTER_API_KEY", "dummy_token_for_local_vllm"),
        "extra_params": {},
    },
    "deepseek-r1": {
        "api_url": "https://openrouter.ai/api/v1/chat/completions",
        "model_name": "deepseek/deepseek-r1",
        "api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "extra_params": {"reasoning": {"effort": "none"}},
    },
}

JUDGE_HEADERS: dict[str, str] = {
    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}",
    "HTTP-Referer": "http://localhost",
    "Content-Type": "application/json",
}

# ============================================================
# Paths
# ============================================================

CASES_FILE_DEFAULT = ROOT / "data" / "processed" / "experiment_cases_full.jsonl"
OUTPUT_DIR = ROOT / "data" / "outputs" / "main_experiment"


# ============================================================
# API call
# ============================================================


async def call_model(
    session: aiohttp.ClientSession,
    model_cfg: dict,
    messages: list[dict],
) -> str:
    """Call target model API with retry logic.

    Args:
        session: aiohttp session.
        model_cfg: Model configuration dict.
        messages: Message list.

    Returns:
        Model response content string.
    """
    headers = {
        "Authorization": f"Bearer {model_cfg['api_key']}",
        "HTTP-Referer": "http://localhost",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_cfg["model_name"],
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 512,
        **model_cfg.get("extra_params", {}),
    }

    for attempt in range(3):
        try:
            async with session.post(
                model_cfg["api_url"], headers=headers, json=payload
            ) as resp:
                if resp.status == 429:
                    wait = 2**attempt * 10
                    logger.warning("Rate limited, waiting %ds", wait)
                    await asyncio.sleep(wait)
                    continue

                result = await resp.json()
                if "choices" in result and result["choices"]:
                    return result["choices"][0]["message"]["content"]

                error = result.get("error", {}).get("message", str(result))
                logger.warning("API error: %s", error)
                await asyncio.sleep(2**attempt)

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning("Request failed (attempt %d): %s", attempt + 1, e)
            await asyncio.sleep(2**attempt)

    return "[ERROR] All retries failed"


# ============================================================
# Single case execution
# ============================================================


async def run_single_case(
    session: aiohttp.ClientSession,
    judge_session: aiohttp.ClientSession,
    model_cfg: dict,
    case: dict,
    rep: int,
) -> dict:
    """Run multi-turn inference for a single case, scoring each turn.

    Args:
        session: aiohttp session for model inference.
        judge_session: aiohttp session for LLM-judge.
        model_cfg: Model configuration.
        case: Experiment case dict.
        rep: Repetition number (0-indexed).

    Returns:
        Complete result record with per-turn scores.
    """
    case_id = case["case_id"]
    system_prompt = case["system_prompt"]
    rules = case["rules"]
    turns = case["conversation_template"]
    model_name = model_cfg["model_name"]

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    turn_results: list[dict] = []

    for turn_info in turns:
        turn_num = turn_info["turn"]
        user_content = turn_info["content"]
        messages.append({"role": "user", "content": user_content})

        # Get model response
        response = await call_model(session, model_cfg, messages)
        messages.append({"role": "assistant", "content": response})

        # Phase 1: Sync auto-scoring (behavioral rules return pending)
        scores = score_rules(response, rules)

        # Phase 2: Async LLM-judge for pending behavioral rules
        for i, score_result in enumerate(scores):
            if score_result["method"] == "llm_judge" and score_result["pass"] is None:
                if "pending" in score_result.get("detail", ""):
                    judge_result = await score_behavioral_async(
                        judge_session,
                        JUDGE_HEADERS,
                        response,
                        rules[i],
                        user_content,
                    )
                    scores[i] = judge_result

        compliance = compute_compliance_rate(scores)

        turn_results.append({
            "turn": turn_num,
            "user_message": user_content,
            "response": response,
            "scores": scores,
            "compliance_rate": compliance,
            "response_length": len(response),
        })

        # Rate limit spacing for OpenRouter models
        if "openrouter" in model_cfg["api_url"]:
            await asyncio.sleep(1.5)
        else:
            await asyncio.sleep(0.3)

    return {
        "case_id": case_id,
        "rep": rep,
        "model": model_name,
        "research_question": case.get("research_question", ""),
        "rule_count": case["rule_count"],
        "turn_count": case["turn_count"],
        "attack_intensity": case["attack_intensity"],
        "rule_set_variant": case.get("rule_set_variant", []),
        "turn_results": turn_results,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


# ============================================================
# Main runner
# ============================================================


def load_checkpoint(output_path: Path) -> set[str]:
    """Load completed run IDs from checkpoint file."""
    completed: set[str] = set()
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    run_id = f"{rec['case_id']}_{rec['rep']}_{rec['model']}"
                    completed.add(run_id)
    return completed


async def run_experiment(
    models: list[str],
    reps: int = 5,
    dry_run: bool = False,
    cases_file: str | None = None,
) -> None:
    """Run the full experiment.

    Args:
        models: List of model keys from MODEL_CONFIGS.
        reps: Number of repetitions per case.
        dry_run: If True, only run first 5 cases.
        cases_file: Path to cases JSONL (default: experiment_cases_full.jsonl).
    """
    cases_path = Path(cases_file) if cases_file else CASES_FILE_DEFAULT
    if not cases_path.exists():
        logger.error("Cases file not found: %s", cases_path)
        logger.error("Run: python scripts/generate_full_cases.py")
        return

    cases: list[dict] = []
    with open(cases_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))

    if dry_run:
        cases = cases[:5]
        reps = 1

    total_cases = len(cases)
    total_runs = total_cases * reps * len(models)
    logger.info(
        "Experiment: %d cases × %d reps × %d models = %d runs",
        total_cases, reps, len(models), total_runs,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for model_key in models:
        if model_key not in MODEL_CONFIGS:
            logger.error("Unknown model: %s (available: %s)", model_key, list(MODEL_CONFIGS.keys()))
            continue

        model_cfg = MODEL_CONFIGS[model_key]
        model_slug = model_cfg["model_name"].replace("/", "_")
        output_path = OUTPUT_DIR / f"results_{model_slug}.jsonl"

        # Load checkpoint
        completed = load_checkpoint(output_path)
        logger.info(
            "Model %s: %d already completed, output → %s",
            model_key, len(completed), output_path,
        )

        timeout = aiohttp.ClientTimeout(total=180, connect=30)
        judge_timeout = aiohttp.ClientTimeout(total=120, connect=30)

        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            aiohttp.ClientSession(timeout=judge_timeout) as judge_session,
        ):
            run_count = 0
            skip_count = 0

            for rep in range(reps):
                for case in cases:
                    run_id = f"{case['case_id']}_{rep}_{model_cfg['model_name']}"
                    if run_id in completed:
                        skip_count += 1
                        continue

                    run_count += 1
                    logger.info(
                        "[%d/%d] %s rep=%d model=%s (R%d T%d %s)",
                        run_count,
                        total_runs - skip_count,
                        case["case_id"],
                        rep,
                        model_key,
                        case["rule_count"],
                        case["turn_count"],
                        case["attack_intensity"],
                    )

                    try:
                        result = await run_single_case(
                            session, judge_session, model_cfg, case, rep
                        )

                        # Append to output (streaming checkpoint)
                        with open(output_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps(result, ensure_ascii=False) + "\n")

                        # Log compliance summary
                        final_compliance = (
                            result["turn_results"][-1]["compliance_rate"]
                            if result["turn_results"]
                            else 0.0
                        )
                        logger.info(
                            "  → final compliance: %.0f%% (%d turns)",
                            final_compliance * 100,
                            len(result["turn_results"]),
                        )

                    except Exception as e:
                        logger.error(
                            "FAILED %s rep=%d: %s", case["case_id"], rep, e
                        )

            logger.info(
                "Model %s complete: %d runs, %d skipped",
                model_key, run_count, skip_count,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run compliance decay experiment.")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["vllm"],
        choices=list(MODEL_CONFIGS.keys()),
        help="Models to evaluate.",
    )
    parser.add_argument(
        "--reps",
        type=int,
        default=5,
        help="Repetitions per case (default: 5).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run only 5 cases with 1 rep for validation.",
    )
    parser.add_argument(
        "--cases-file",
        type=str,
        default=None,
        help="Path to experiment cases JSONL (default: experiment_cases_full.jsonl).",
    )
    args = parser.parse_args()

    asyncio.run(run_experiment(args.models, args.reps, args.dry_run, args.cases_file))


if __name__ == "__main__":
    main()

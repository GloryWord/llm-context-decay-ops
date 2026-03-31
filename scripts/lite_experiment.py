"""Lite pilot experiment: 5 cases × multi-turn inference + scoring + visualization.

Runs 5 representative cases from sample_cases_v4.jsonl via OpenRouter API,
scores each turn's response, and produces a visual report.

Usage:
    source /tmp/experiment-env/bin/activate
    python scripts/lite_experiment.py
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import aiohttp

# Add project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.evaluation.compliance_scorer import compute_compliance_rate, score_rules

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- Config ---
API_URL = os.getenv("VLLM_API_URL", "http://210.179.28.26:18000/v1/chat/completions")
MODEL = os.getenv("EVAL_MODEL_NAME", "meta-llama/Meta-Llama-3.1-8B-Instruct")
SELECTED_CASES = ["v4_001", "v4_002", "v4_003", "v4_006", "v4_008"]
CASES_FILE = ROOT / "data" / "processed" / "sample_cases_v4.jsonl"
OUTPUT_DIR = ROOT / "data" / "outputs" / "lite_pilot"
REPORT_DIR = ROOT / "docs" / "outputs"


async def call_api(
    session: aiohttp.ClientSession,
    headers: dict,
    messages: list[dict],
) -> str:
    """Single API call with retry."""
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 512,
    }
    for attempt in range(3):
        try:
            async with session.post(API_URL, headers=headers, json=payload) as resp:
                if resp.status == 429:
                    wait = 2 ** attempt * 10
                    logger.warning("Rate limited, waiting %ds", wait)
                    await asyncio.sleep(wait)
                    continue
                result = await resp.json()
                if "choices" in result and result["choices"]:
                    return result["choices"][0]["message"]["content"]
                error = result.get("error", {}).get("message", str(result))
                logger.warning("API error: %s", error)
                await asyncio.sleep(2 ** attempt)
        except Exception as e:
            logger.warning("Request failed (attempt %d): %s", attempt + 1, e)
            await asyncio.sleep(2 ** attempt)
    return "[ERROR] All retries failed"


async def run_case(
    session: aiohttp.ClientSession,
    headers: dict,
    case: dict,
) -> dict:
    """Run multi-turn inference for a single case, scoring each turn."""
    case_id = case["case_id"]
    system_prompt = case["system_prompt"]
    rules = case["rules"]
    turns = case["conversation_template"]

    logger.info("Running %s: %d rules, %d turns, %s",
                case_id, case["rule_count"], len(turns), case["attack_intensity"])

    messages = [{"role": "system", "content": system_prompt}]
    turn_results = []

    for turn_info in turns:
        turn_num = turn_info["turn"]
        user_content = turn_info["content"]
        messages.append({"role": "user", "content": user_content})

        response = await call_api(session, headers, messages)
        messages.append({"role": "assistant", "content": response})

        # Score this turn
        scores = score_rules(response, rules)
        rate = compute_compliance_rate(scores)

        turn_results.append({
            "turn": turn_num,
            "response": response,
            "scores": scores,
            "compliance_rate": rate,
            "response_length": len(response),
        })

        logger.info("  Turn %d: compliance=%.0f%% (%d chars)",
                     turn_num, rate * 100, len(response))

        # Small delay to avoid rate limits
        await asyncio.sleep(1)

    return {
        "case_id": case_id,
        "research_question": case["research_question"],
        "rule_count": case["rule_count"],
        "turn_count": len(turns),
        "attack_intensity": case["attack_intensity"],
        "model": MODEL,
        "turn_results": turn_results,
        "system_prompt": system_prompt,
        "rules": rules,
    }


async def main():
    api_key = os.getenv("OPENROUTER_API_KEY", "dummy_token_for_local_vllm")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "http://localhost",
        "Content-Type": "application/json",
    }

    # Load selected cases
    cases = []
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                c = json.loads(line)
                if c["case_id"] in SELECTED_CASES:
                    cases.append(c)

    logger.info("Loaded %d cases", len(cases))

    # Run inference
    all_results = []
    timeout = aiohttp.ClientTimeout(total=120, connect=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for case in cases:
            result = await run_case(session, headers, case)
            all_results.append(result)

    # Save raw results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results_file = OUTPUT_DIR / "lite_results.jsonl"
    with open(results_file, "w", encoding="utf-8") as f:
        for r in all_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    logger.info("Results saved to %s", results_file)

    # Generate visualization
    generate_charts(all_results)

    # Generate report
    generate_report(all_results)

    logger.info("Done. Report at %s", REPORT_DIR / "lite_pilot_report.md")


def generate_charts(results: list[dict]):
    """Generate visualization charts."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    import seaborn as sns

    sns.set_theme(style="whitegrid", palette="colorblind")

    # Try to use a Korean-capable font
    korean_font = None
    for font_name in ["AppleGothic", "NanumGothic", "Malgun Gothic", "Arial Unicode MS"]:
        if any(font_name in f.name for f in fm.fontManager.ttflist):
            korean_font = font_name
            break
    if korean_font:
        plt.rcParams["font.family"] = korean_font
    plt.rcParams["axes.unicode_minus"] = False

    fig_dir = ROOT / "docs" / "outputs" / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    # --- Chart 1: Compliance rate over turns (all cases) ---
    fig, ax = plt.subplots(figsize=(10, 6))
    for r in results:
        turns = [t["turn"] for t in r["turn_results"]]
        rates = [t["compliance_rate"] * 100 for t in r["turn_results"]]
        label = f"{r['case_id']} (R{r['rule_count']}, {r['attack_intensity']})"
        ax.plot(turns, rates, marker="o", linewidth=2, markersize=6, label=label)

    ax.set_xlabel("Turn", fontsize=12)
    ax.set_ylabel("Compliance Rate (%)", fontsize=12)
    ax.set_title("System Prompt Compliance Over Turns", fontsize=14)
    ax.set_ylim(-5, 105)
    ax.legend(fontsize=9, loc="lower left")
    ax.axhline(y=80, color="orange", linestyle="--", alpha=0.5, label="80% threshold")
    ax.axhline(y=50, color="red", linestyle="--", alpha=0.5, label="50% threshold")
    plt.tight_layout()
    plt.savefig(fig_dir / "compliance_over_turns.png", dpi=150)
    plt.close()
    logger.info("Chart saved: compliance_over_turns.png")

    # --- Chart 2: Per-rule compliance heatmap (v4_003, 5 rules × 10 turns) ---
    case_003 = next((r for r in results if r["case_id"] == "v4_003"), None)
    if case_003:
        rule_ids = [rule["rule_id"] for rule in case_003["rules"]]
        turn_nums = [t["turn"] for t in case_003["turn_results"]]

        matrix = []
        for t in case_003["turn_results"]:
            row = []
            for rid in rule_ids:
                score = next((s for s in t["scores"] if s["rule_id"] == rid), None)
                if score and score["pass"] is True:
                    row.append(1)
                elif score and score["pass"] is False:
                    row.append(0)
                else:
                    row.append(0.5)  # pending/N/A
            matrix.append(row)

        fig, ax = plt.subplots(figsize=(8, 6))
        import numpy as np
        from matplotlib.colors import ListedColormap
        cmap = ListedColormap(["#e74c3c", "#f0e68c", "#2ecc71"])
        bounds = [0, 0.25, 0.75, 1.0]
        from matplotlib.colors import BoundaryNorm
        norm = BoundaryNorm(bounds, cmap.N)

        im = ax.imshow(np.array(matrix), cmap=cmap, norm=norm, aspect="auto")
        ax.set_xticks(range(len(rule_ids)))
        ax.set_xticklabels(rule_ids, fontsize=10)
        ax.set_yticks(range(len(turn_nums)))
        ax.set_yticklabels([f"T{t}" for t in turn_nums], fontsize=10)
        ax.set_xlabel("Rule", fontsize=12)
        ax.set_ylabel("Turn", fontsize=12)
        ax.set_title("v4_003: Per-Rule Compliance (5 rules x 10 turns)", fontsize=13)

        # Legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor="#2ecc71", label="Pass"),
            Patch(facecolor="#f0e68c", label="N/A / Pending"),
            Patch(facecolor="#e74c3c", label="Fail"),
        ]
        ax.legend(handles=legend_elements, loc="upper right", fontsize=9)
        plt.tight_layout()
        plt.savefig(fig_dir / "rule_heatmap_v4_003.png", dpi=150)
        plt.close()
        logger.info("Chart saved: rule_heatmap_v4_003.png")

    # --- Chart 3: Benign vs Adversarial comparison ---
    benign_cases = [r for r in results if r["attack_intensity"] == "benign" and r["turn_count"] >= 5]
    adv_cases = [r for r in results if r["attack_intensity"] == "adversarial"]

    if benign_cases and adv_cases:
        fig, ax = plt.subplots(figsize=(10, 6))
        for r in benign_cases[:2]:
            turns = [t["turn"] for t in r["turn_results"]]
            rates = [t["compliance_rate"] * 100 for t in r["turn_results"]]
            ax.plot(turns, rates, marker="o", linewidth=2, linestyle="-",
                    label=f"{r['case_id']} (benign, R{r['rule_count']})")
        for r in adv_cases:
            turns = [t["turn"] for t in r["turn_results"]]
            rates = [t["compliance_rate"] * 100 for t in r["turn_results"]]
            ax.plot(turns, rates, marker="s", linewidth=2, linestyle="--",
                    label=f"{r['case_id']} (adversarial, R{r['rule_count']})")

        ax.set_xlabel("Turn", fontsize=12)
        ax.set_ylabel("Compliance Rate (%)", fontsize=12)
        ax.set_title("Q3: Benign vs Adversarial Compliance Decay", fontsize=14)
        ax.set_ylim(-5, 105)
        ax.legend(fontsize=9)
        ax.axhline(y=80, color="orange", linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.savefig(fig_dir / "benign_vs_adversarial.png", dpi=150)
        plt.close()
        logger.info("Chart saved: benign_vs_adversarial.png")


def generate_report(results: list[dict]):
    """Generate markdown report."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "lite_pilot_report.md"

    lines = []
    lines.append("# Lite Pilot Experiment Report")
    lines.append("")
    lines.append(f"> **Date**: {time.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"> **Model**: `{MODEL}`")
    lines.append(f"> **Cases**: {len(results)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary table
    lines.append("## 1. Summary")
    lines.append("")
    lines.append("| Case | RQ | Rules | Turns | Attack | Final Compliance | First Drop <80% |")
    lines.append("|------|-----|-------|-------|--------|-----------------|-----------------|")

    for r in results:
        turn_results = r["turn_results"]
        final_rate = turn_results[-1]["compliance_rate"] * 100
        first_drop = "—"
        for t in turn_results:
            if t["compliance_rate"] < 0.8:
                first_drop = f"Turn {t['turn']}"
                break

        lines.append(
            f"| {r['case_id']} | {r['research_question']} | {r['rule_count']} | "
            f"{r['turn_count']} | {r['attack_intensity']} | {final_rate:.0f}% | {first_drop} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # Charts
    lines.append("## 2. Visualizations")
    lines.append("")
    lines.append("### 2.1 Compliance Over Turns")
    lines.append("![Compliance Over Turns](figures/compliance_over_turns.png)")
    lines.append("")
    lines.append("### 2.2 Per-Rule Heatmap (v4_003: 5 rules x 10 turns)")
    lines.append("![Rule Heatmap](figures/rule_heatmap_v4_003.png)")
    lines.append("")
    lines.append("### 2.3 Benign vs Adversarial (Q3)")
    lines.append("![Benign vs Adversarial](figures/benign_vs_adversarial.png)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Per-case detail
    lines.append("## 3. Per-Case Detail")
    lines.append("")

    for r in results:
        lines.append(f"### {r['case_id']} ({r['research_question']}, {r['attack_intensity']})")
        lines.append("")
        lines.append(f"- **Rules**: {r['rule_count']} | **Turns**: {r['turn_count']}")
        lines.append("")
        lines.append("| Turn | Compliance | Rule Results |")
        lines.append("|------|-----------|-------------|")

        for t in r["turn_results"]:
            rate = t["compliance_rate"] * 100
            rule_detail = " ".join(
                f"`{s['rule_id']}:{'P' if s['pass'] is True else 'F' if s['pass'] is False else '?'}`"
                for s in t["scores"]
            )
            lines.append(f"| {t['turn']} | {rate:.0f}% | {rule_detail} |")

        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 4. Observations")
    lines.append("")

    # Auto-generate observations
    # Check for decay patterns
    all_final_rates = [(r["case_id"], r["rule_count"], r["turn_results"][-1]["compliance_rate"])
                       for r in results]
    decayed = [(cid, rc, rate) for cid, rc, rate in all_final_rates if rate < 1.0]

    if decayed:
        lines.append("### Compliance Decay Detected")
        for cid, rc, rate in decayed:
            lines.append(f"- **{cid}** (rules={rc}): final compliance {rate*100:.0f}%")
        lines.append("")

    # Check adversarial vs benign
    adv = [r for r in results if r["attack_intensity"] == "adversarial"]
    ben = [r for r in results if r["attack_intensity"] == "benign" and r["turn_count"] >= 5]
    if adv and ben:
        avg_adv = sum(r["turn_results"][-1]["compliance_rate"] for r in adv) / len(adv)
        avg_ben = sum(r["turn_results"][-1]["compliance_rate"] for r in ben) / len(ben)
        lines.append("### Adversarial Impact")
        lines.append(f"- Benign avg final compliance: {avg_ben*100:.0f}%")
        lines.append(f"- Adversarial avg final compliance: {avg_adv*100:.0f}%")
        lines.append(f"- Difference: {(avg_ben - avg_adv)*100:.0f}pp")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 5. Limitations")
    lines.append("")
    lines.append("- 5 cases only (pilot, not statistically significant)")
    lines.append("- Single model (`llama-3.1-8b-instruct:free`)")
    lines.append("- `llm_judge` rules scored as N/A (placeholder)")
    lines.append("- No repetition (1 trial per case)")
    lines.append("- Free-tier model may have degraded quality")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("Report saved to %s", report_path)


if __name__ == "__main__":
    asyncio.run(main())

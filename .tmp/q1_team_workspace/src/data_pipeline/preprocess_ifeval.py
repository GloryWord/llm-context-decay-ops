"""Preprocess IFEval dataset for Phase 1 experiments.

Separates format constraints into system prompt rules and task content
into probe messages. Only keeps auto-scorable instruction types.

Usage:
    python -m src.data_pipeline.preprocess_ifeval --config configs/preprocess.yaml
"""

import argparse
import json
import logging
import re
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# Mapping from instruction type to scoring function description
SCORING_FUNCTIONS: dict[str, str] = {
    "keywords:forbidden_words": "response must NOT contain any of the forbidden words",
    "keywords:existence": "response must contain ALL specified keywords",
    "keywords:frequency": "specified keyword must appear exactly N times",
    "keywords:letter_frequency": "specified letter must appear at least N times",
    "detectable_format:json_format": "response must be valid JSON",
    "detectable_format:number_bullets": "response must contain exactly N bullet points",
    "detectable_format:number_highlighted_sections": (
        "response must contain exactly N highlighted sections"
    ),
    "detectable_format:title": "response must include a title in markdown format",
    "detectable_content:number_placeholders": (
        "response must contain exactly N placeholder brackets [...]"
    ),
    "detectable_content:postscript": "response must include a postscript starting with P.S.",
    "length_constraints:number_sentences": "response must contain exactly N sentences",
    "length_constraints:number_paragraphs": "response must contain exactly N paragraphs",
    "length_constraints:number_words": "response must contain at least N words",
    "change_case:english_lowercase": "entire response must be in lowercase",
    "change_case:english_capital": "entire response must be in uppercase",
    "punctuation:no_comma": "response must NOT contain any commas",
    "startend:end_checker": "response must end with the specified phrase",
    "startend:quotation": "response must be wrapped in double quotation marks",
}


def extract_constraints(prompt: str, instruction_id_list: list[str]) -> list[dict]:
    """Extract format constraints from IFEval prompt text.

    Identifies instruction-following constraints embedded in the prompt
    and separates them from the task content.

    Args:
        prompt: Full IFEval prompt text.
        instruction_id_list: List of instruction type IDs for this prompt.

    Returns:
        List of constraint dicts with 'type' and 'description'.
    """
    constraints = []
    for inst_type in instruction_id_list:
        scoring_desc = SCORING_FUNCTIONS.get(inst_type)
        if scoring_desc:
            constraints.append({
                "type": inst_type,
                "scoring_description": scoring_desc,
            })
    return constraints


def separate_task_and_rules(prompt: str) -> tuple[str, str]:
    """Heuristically separate task content from format instructions.

    IFEval prompts typically have a task description followed by
    format constraints. This function splits them.

    Args:
        prompt: Full IFEval prompt.

    Returns:
        Tuple of (task_content, format_rules_text).
    """
    # Common constraint signal phrases
    constraint_signals = [
        r"your (?:response|answer|entire response|output) (?:should|must|needs to)",
        r"(?:make sure|ensure|please ensure|be sure)",
        r"do not (?:use|include|contain)",
        r"(?:use|include|write) (?:at least|exactly|no more than)",
        r"wrap your (?:response|answer)",
        r"(?:highlight|format) (?:at least|exactly)",
        r"your (?:entire )?(?:response|reply) should be in",
        r"end (?:your response|the response) with",
        r"(?:answer|respond|reply) in (?:all )?(?:lowercase|uppercase|capital)",
    ]

    combined_pattern = "|".join(f"({p})" for p in constraint_signals)

    # Find the earliest constraint signal
    match = re.search(combined_pattern, prompt, re.IGNORECASE)
    if match:
        # Split at sentence boundary before the match
        split_pos = match.start()
        # Walk back to find sentence boundary
        before = prompt[:split_pos]
        last_period = max(before.rfind(". "), before.rfind(".\n"), before.rfind("?\n"))
        if last_period > 0:
            split_pos = last_period + 1

        task_content = prompt[:split_pos].strip()
        format_rules = prompt[split_pos:].strip()
    else:
        # No clear separation found — treat entire prompt as task
        task_content = prompt
        format_rules = ""

    return task_content, format_rules


def build_system_prompt(format_rules: str, constraints: list[dict]) -> str:
    """Build a system prompt from extracted format rules.

    Args:
        format_rules: Raw format instruction text from the prompt.
        constraints: Parsed constraint list.

    Returns:
        System prompt string.
    """
    if not format_rules and not constraints:
        return ""

    rules_text = format_rules if format_rules else "; ".join(
        c["scoring_description"] for c in constraints
    )
    return (
        "You must follow these formatting rules strictly when responding:\n"
        f"{rules_text}"
    )


def preprocess_ifeval(config_path: str) -> list[dict]:
    """Run full IFEval preprocessing pipeline.

    Args:
        config_path: Path to preprocess.yaml.

    Returns:
        List of processed probe records.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    raw_dir = Path(cfg["paths"]["raw_dir"])
    processed_dir = Path(cfg["paths"]["processed_dir"])
    ifeval_cfg = cfg["ifeval_preprocess"]

    input_file = raw_dir / cfg["datasets"]["ifeval"]["raw_subdir"] / "ifeval.jsonl"
    if not input_file.exists():
        logger.error("IFEval data not found at %s", input_file)
        return []

    auto_scorable = set(ifeval_cfg["auto_scorable_types"])
    max_probes = ifeval_cfg.get("max_probes", 20)

    all_probes: list[dict] = []
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            record = json.loads(line)
            prompt = record.get("prompt", "")
            instruction_id_list = record.get("instruction_id_list", [])
            kwargs_list = record.get("kwargs", [])

            if not prompt or not instruction_id_list:
                continue

            # Filter: only keep records where ALL instructions are auto-scorable
            if not all(iid in auto_scorable for iid in instruction_id_list):
                continue

            # Separate task content from format constraints
            task_content, format_rules = separate_task_and_rules(prompt)
            constraints = extract_constraints(prompt, instruction_id_list)

            if not constraints:
                continue

            system_prompt = build_system_prompt(format_rules, constraints)
            probe_id = f"ifeval_{len(all_probes)}"

            probe = {
                "probe_id": probe_id,
                "probe_dataset": "ifeval",
                "instruction_types": instruction_id_list,
                "system_prompt": system_prompt,
                "probe_messages": [{"role": "user", "content": task_content}],
                "constraints": constraints,
                "kwargs": kwargs_list,
                "rule_count": len(constraints),
                "rule_count_level": len(constraints),
                "probe_intensity": "basic",
                "scoring_type": "rule_based",
                "scoring_check": "; ".join(c["scoring_description"] for c in constraints),
            }
            all_probes.append(probe)

            if len(all_probes) >= max_probes:
                break

    # Write output
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_path = processed_dir / "ifeval_probes.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for probe in all_probes:
            f.write(json.dumps(probe, ensure_ascii=False) + "\n")

    logger.info("Wrote %d IFEval probes to %s", len(all_probes), output_path)
    return all_probes


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Preprocess IFEval dataset.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/preprocess.yaml",
        help="Path to preprocess config YAML.",
    )
    args = parser.parse_args()
    preprocess_ifeval(args.config)

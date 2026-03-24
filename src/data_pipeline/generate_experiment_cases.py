"""Generate experiment cases for v2 experiments.

Combines Project Aegis probes with ShareGPT/MultiChallenge intermediate turns
to produce experiment cases covering all conditions.

v2 key changes:
- Project Aegis domain-cohesive rule set (replaces hybrid RuLES/IFEval)
- Single user message embedding for Chat Template compliance
- total_context_tokens via final rendered string tokenization (no arithmetic sum)
- Case 3 repurposed as Alignment Tax measurement
- Variables: turn_counts [0,2,4,6,8], rule_count_levels [1,3,5,10,15,20]

Case types:
- Baseline (turns=0): rule_count(6) × probe count = ~24
- Normal (ShareGPT): turn(4) × rule_count(6) × token_length(3) × probe count = ~288
- Case 3 (Alignment Tax): rule_count(7) × MC conversations = separate

Usage:
    python -m src.data_pipeline.generate_experiment_cases --config configs/preprocess.yaml
"""

import argparse
import json
import logging
from pathlib import Path

import yaml

from src.data_pipeline.token_utils import count_tokens

logger = logging.getLogger(__name__)


def load_jsonl(path: Path) -> list[dict]:
    """Load records from a JSONL file.

    Args:
        path: Path to the JSONL file.

    Returns:
        List of parsed dicts.
    """
    records = []
    if not path.exists():
        logger.warning("File not found: %s", path)
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def render_embedded_user_message(
    user_turns: list[str],
    probe_question: str,
) -> str:
    """Render intermediate user turns + probe into a single user message.

    Embeds conversation history in a single message to comply with
    Chat Template alternating turns requirement.

    Args:
        user_turns: List of user turn content strings.
        probe_question: The probe question to append.

    Returns:
        Single user message string.
    """
    if not user_turns:
        return probe_question

    history_lines = [f"User: {turn}" for turn in user_turns]
    history_text = "\n".join(history_lines)

    return (
        "다음은 이전 대화 기록입니다.\n\n"
        "[대화 기록 시작]\n"
        f"{history_text}\n"
        "[대화 기록 끝]\n\n"
        "위 기록을 참고하여 다음 질문에 답하세요:\n"
        f"{probe_question}"
    )


def select_sharegpt_turns(
    turns_pool: list[dict],
    target_count: int,
) -> list[str]:
    """Select user turn contents from ShareGPT pool.

    Args:
        turns_pool: Available ShareGPT turn records.
        target_count: Number of user turns needed.

    Returns:
        List of user turn content strings.
    """
    if not turns_pool or target_count <= 0:
        return []

    selected = []
    pool_size = len(turns_pool)
    for i in range(target_count):
        turn = turns_pool[i % pool_size]
        selected.append(turn["content"])

    return selected


def build_case(
    case_id: str,
    condition: dict,
    probe: dict,
    rendered_user_message: str,
    intermediate_turns_type: str,
) -> dict:
    """Build a single experiment case with token counts.

    Args:
        case_id: Unique case identifier.
        condition: Condition variable dict.
        probe: Selected probe record.
        rendered_user_message: Final rendered user message (history + probe).
        intermediate_turns_type: 'none', 'user_only_embedded', or 'full'.

    Returns:
        Complete experiment case dict.
    """
    system_prompt = probe.get("system_prompt", "")

    # Token counting: tokenize final rendered strings, NOT arithmetic sum
    system_prompt_tokens = count_tokens(system_prompt)
    user_message_tokens = count_tokens(rendered_user_message)
    total_context_tokens = system_prompt_tokens + user_message_tokens

    return {
        "case_id": case_id,
        "condition": condition,
        "system_prompt": system_prompt,
        "rendered_user_message": rendered_user_message,
        "intermediate_turns_type": intermediate_turns_type,
        "probe_id": probe.get("probe_id", ""),
        "target_rule": probe.get("target_rule", 0),
        "scoring": {
            "type": probe.get("scoring_type", "programmatic"),
            "dataset": probe.get("probe_dataset", ""),
            "check_description": probe.get("scoring_check", ""),
            "target_rule": probe.get("target_rule", 0),
            "rule_ids": probe.get("rule_ids", []),
        },
        "token_counts": {
            "system_prompt_tokens": system_prompt_tokens,
            "user_message_tokens": user_message_tokens,
            "total_context_tokens": total_context_tokens,
        },
    }


def generate_cases(config_path: str) -> list[dict]:
    """Generate all experiment cases from preprocessed data.

    Args:
        config_path: Path to preprocess.yaml.

    Returns:
        List of experiment case dicts.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    processed_dir = Path(cfg["paths"]["processed_dir"])
    exp_cfg = cfg["experiment"]

    # Load preprocessed data
    aegis_probes = load_jsonl(processed_dir / "aegis_probes.jsonl")
    sharegpt_short = load_jsonl(processed_dir / "sharegpt_turns_short.jsonl")
    sharegpt_medium = load_jsonl(processed_dir / "sharegpt_turns_medium.jsonl")
    sharegpt_long = load_jsonl(processed_dir / "sharegpt_turns_long.jsonl")
    mc_conversations = load_jsonl(
        processed_dir / "multichallenge_conversations.jsonl"
    )

    logger.info(
        "Loaded: %d Aegis probes, %d short, %d medium, %d long turns, "
        "%d MC conversations",
        len(aegis_probes),
        len(sharegpt_short),
        len(sharegpt_medium),
        len(sharegpt_long),
        len(mc_conversations),
    )

    turn_counts = exp_cfg["turn_counts"]
    rule_levels = exp_cfg["rule_count_levels"]
    token_lengths = exp_cfg["token_lengths"]

    sharegpt_pools = {
        "short": sharegpt_short,
        "medium": sharegpt_medium,
        "long": sharegpt_long,
    }

    # Index probes by (rule_count_level, probe_intensity), limit to probes_per_condition
    probes_per_cond = exp_cfg.get("probes_per_condition", 2)
    probe_index: dict[tuple[int, str], list[dict]] = {}
    for probe in aegis_probes:
        key = (probe["rule_count_level"], probe["probe_intensity"])
        probe_index.setdefault(key, [])
        if len(probe_index[key]) < probes_per_cond:
            probe_index[key].append(probe)

    all_cases: list[dict] = []
    case_counter = 0

    # --- Case 1 (Baseline) & Case 2 (Normal) ---
    for turn_count in turn_counts:
        for rule_level in rule_levels:
            for intensity in ("basic", "redteam"):
                probes = probe_index.get((rule_level, intensity), [])
                if not probes:
                    logger.warning(
                        "No probes for rule=%d, intensity=%s",
                        rule_level,
                        intensity,
                    )
                    continue

                if turn_count == 0:
                    # Baseline — no intermediate turns
                    condition = {
                        "turn_count": 0,
                        "difficulty": "baseline",
                        "rule_count_level": rule_level,
                        "probe_intensity": intensity,
                        "token_length": "none",
                    }

                    for probe in probes:
                        probe_question = probe["probe_messages"][0]["content"]
                        rendered = render_embedded_user_message([], probe_question)

                        case_id = f"exp_{case_counter:04d}"
                        case = build_case(
                            case_id,
                            condition,
                            probe,
                            rendered,
                            intermediate_turns_type="none",
                        )
                        all_cases.append(case)
                        case_counter += 1

                else:
                    # Normal (ShareGPT) — varies by token_length
                    for token_len in token_lengths:
                        condition = {
                            "turn_count": turn_count,
                            "difficulty": "normal",
                            "rule_count_level": rule_level,
                            "probe_intensity": intensity,
                            "token_length": token_len,
                        }

                        pool = sharegpt_pools.get(token_len, sharegpt_short)
                        user_turns = select_sharegpt_turns(pool, turn_count)

                        for probe in probes:
                            probe_question = probe["probe_messages"][0]["content"]
                            rendered = render_embedded_user_message(
                                user_turns, probe_question
                            )

                            case_id = f"exp_{case_counter:04d}"
                            case = build_case(
                                case_id,
                                condition,
                                probe,
                                rendered,
                                intermediate_turns_type="user_only_embedded",
                            )
                            all_cases.append(case)
                            case_counter += 1

    # --- Case 3: Alignment Tax (MultiChallenge) ---
    # Separate measurement: rule_count(0,1,3,5,10,15,20) × MC conversations
    # Full turns preserved, measures Task Accuracy not Compliance
    alignment_tax_levels = [0] + rule_levels
    aegis_cfg = cfg.get("project_aegis", {})
    level_rule_map = aegis_cfg.get("rule_count_levels", {})

    for rule_level in alignment_tax_levels:
        for mc_idx, mc_conv in enumerate(mc_conversations):
            condition = {
                "turn_count": len(
                    [t for t in mc_conv.get("turns", []) if t["role"] == "user"]
                ),
                "difficulty": "alignment_tax",
                "rule_count_level": rule_level,
                "probe_intensity": "task",
                "token_length": "fixed",
            }

            # Build system prompt: 0 rules = no system prompt
            if rule_level == 0:
                system_prompt = ""
            else:
                from src.data_pipeline.generate_multi_rule_probes import (
                    render_system_prompt,
                )

                rule_ids = [
                    int(r)
                    for r in level_rule_map.get(
                        rule_level, level_rule_map.get(str(rule_level), [])
                    )
                ]
                system_prompt = render_system_prompt(rule_ids) if rule_ids else ""

            # Keep full conversation turns as-is
            turns = mc_conv.get("turns", [])

            system_tokens = count_tokens(system_prompt) if system_prompt else 0
            turns_text = "\n".join(
                f"{t['role']}: {t['content']}" for t in turns
            )
            turns_tokens = count_tokens(turns_text) if turns_text else 0

            case_id = f"at_{case_counter:04d}"
            case = {
                "case_id": case_id,
                "condition": condition,
                "system_prompt": system_prompt,
                "intermediate_turns": turns,
                "intermediate_turns_type": "full",
                "scoring": {
                    "type": "task_accuracy",
                    "dataset": "multichallenge",
                    "check_description": "MultiChallenge original evaluation",
                    "mc_conversation_id": mc_conv.get("conversation_id", mc_idx),
                },
                "token_counts": {
                    "system_prompt_tokens": system_tokens,
                    "turns_tokens": turns_tokens,
                    "total_context_tokens": system_tokens + turns_tokens,
                },
            }
            all_cases.append(case)
            case_counter += 1

    # Write output
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_path = processed_dir / "experiment_cases.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for case in all_cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")

    _log_summary(all_cases)
    logger.info("Wrote %d experiment cases to %s", len(all_cases), output_path)
    return all_cases


def _log_summary(cases: list[dict]) -> None:
    """Log a summary of generated experiment cases.

    Args:
        cases: List of all generated cases.
    """
    by_difficulty: dict[str, int] = {}
    by_turn: dict[int, int] = {}
    by_rule: dict[int, int] = {}
    token_totals: list[int] = []

    for c in cases:
        cond = c["condition"]
        diff = cond["difficulty"]
        tc = cond["turn_count"]
        rc = cond["rule_count_level"]
        by_difficulty[diff] = by_difficulty.get(diff, 0) + 1
        by_turn[tc] = by_turn.get(tc, 0) + 1
        by_rule[rc] = by_rule.get(rc, 0) + 1

        total_tok = c.get("token_counts", {}).get("total_context_tokens", 0)
        if total_tok:
            token_totals.append(total_tok)

    logger.info("Cases by difficulty: %s", by_difficulty)
    logger.info("Cases by turn_count: %s", dict(sorted(by_turn.items())))
    logger.info("Cases by rule_count: %s", dict(sorted(by_rule.items())))

    if token_totals:
        logger.info(
            "Total context tokens — min: %d, max: %d, mean: %.0f",
            min(token_totals),
            max(token_totals),
            sum(token_totals) / len(token_totals),
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Generate experiment cases.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/preprocess.yaml",
        help="Path to preprocess config YAML.",
    )
    args = parser.parse_args()
    generate_cases(args.config)

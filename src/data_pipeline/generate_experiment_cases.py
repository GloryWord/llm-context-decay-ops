"""Generate experiment cases by combining preprocessed data.

Combines RuLES/IFEval/multi-rule probes with ShareGPT/MultiChallenge
intermediate turns to produce ~260 experiment cases covering all conditions.

v2 variable system:
- turn_counts: [0, 2, 4, 6]
- rule_count_levels: [1, 3, 5, 10, 20]
- token_lengths: [short, medium, long]
- difficulty: baseline, normal, hard
- probe_intensity: basic, redteam

Case types:
- Baseline (turns=0): rule_count(5) x probe_intensity(2) x probe_set(2) = 20
- Normal: turn(3) x rule_count(5) x probe_intensity(2) x token_length(3) x probe_set(2) = 180
- Hard: turn(3) x rule_count(5) x probe_intensity(2) x probe_set(2) = 60
- Total: ~260 cases

Usage:
    python -m src.data_pipeline.generate_experiment_cases --config configs/preprocess.yaml
"""

import argparse
import json
import logging
from pathlib import Path

import yaml

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


def select_probe(
    probes: list[dict],
    rule_count_level: int,
    probe_intensity: str,
) -> dict | None:
    """Select a probe matching the given conditions.

    Args:
        probes: List of probe records.
        rule_count_level: Target rule count (1, 3, 5, 10, 20).
        probe_intensity: 'basic' or 'redteam'.

    Returns:
        Matching probe dict, or None.
    """
    # Exact match on rule_count_level and probe_intensity
    candidates = [
        p for p in probes
        if p.get("rule_count_level") == rule_count_level
        and p.get("probe_intensity") == probe_intensity
    ]
    if candidates:
        return candidates[0]

    # Fallback: match rule_count_level only
    candidates = [
        p for p in probes
        if p.get("rule_count_level") == rule_count_level
    ]
    if candidates:
        return candidates[0]

    # Fallback: closest rule count
    candidates = sorted(
        probes,
        key=lambda p: abs(p.get("rule_count_level", 0) - rule_count_level),
    )
    return candidates[0] if candidates else None


def select_intermediate_turns(
    turns_pool: list[dict],
    target_count: int,
) -> list[dict]:
    """Select intermediate turns from a pool to fill the target turn count.

    Args:
        turns_pool: Available turn records.
        target_count: Number of user turns needed.

    Returns:
        List of selected turn message dicts.
    """
    if not turns_pool or target_count <= 0:
        return []

    selected = []
    pool_size = len(turns_pool)
    for i in range(target_count):
        turn = turns_pool[i % pool_size]
        if "content" in turn:
            selected.append({"role": "user", "content": turn["content"]})
        elif "turns" in turn:
            for msg in turn["turns"]:
                selected.append(msg)
                if len([s for s in selected if s["role"] == "user"]) >= target_count:
                    break
        if len([s for s in selected if s["role"] == "user"]) >= target_count:
            break

    return selected


def select_multichallenge_turns(
    conversations: list[dict],
    target_user_turns: int,
) -> list[dict]:
    """Select full user+assistant turns from MultiChallenge conversations.

    Args:
        conversations: MultiChallenge conversation records.
        target_user_turns: Target number of user turns.

    Returns:
        List of turn dicts with role and content.
    """
    if not conversations or target_user_turns <= 0:
        return []

    selected: list[dict] = []
    user_count = 0
    conv_idx = 0

    while user_count < target_user_turns and conv_idx < len(conversations):
        conv = conversations[conv_idx]
        for turn in conv.get("turns", []):
            selected.append(turn)
            if turn["role"] == "user":
                user_count += 1
            if user_count >= target_user_turns:
                break
        conv_idx += 1

    return selected


def build_case(
    case_id: str,
    condition: dict,
    probe: dict,
    intermediate_turns: list[dict],
    intermediate_turns_type: str,
) -> dict:
    """Build a single experiment case.

    Args:
        case_id: Unique case identifier.
        condition: Condition variable dict.
        probe: Selected probe record.
        intermediate_turns: List of intermediate turn messages.
        intermediate_turns_type: 'none', 'user_only', or 'full'.

    Returns:
        Complete experiment case dict.
    """
    probe_messages = probe.get("probe_messages", [])
    probe_turn = probe_messages[0] if probe_messages else {"role": "user", "content": ""}

    scoring = {
        "type": probe.get("scoring_type", "programmatic"),
        "dataset": probe.get("probe_dataset", ""),
        "check_description": probe.get("scoring_check", ""),
    }
    if probe.get("params"):
        scoring["params"] = probe["params"]
    if probe.get("constraints"):
        scoring["constraints"] = probe["constraints"]
    if probe.get("kwargs"):
        scoring["kwargs"] = probe["kwargs"]

    return {
        "case_id": case_id,
        "condition": condition,
        "system_prompt": probe.get("system_prompt", ""),
        "intermediate_turns": intermediate_turns,
        "intermediate_turns_type": intermediate_turns_type,
        "probe_turn": probe_turn,
        "scoring": scoring,
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
    rules_probes = load_jsonl(processed_dir / "rules_probes.jsonl")
    ifeval_probes = load_jsonl(processed_dir / "ifeval_probes.jsonl")
    multi_rule_probes = load_jsonl(processed_dir / "multi_rule_probes.jsonl")
    sharegpt_short = load_jsonl(processed_dir / "sharegpt_turns_short.jsonl")
    sharegpt_medium = load_jsonl(processed_dir / "sharegpt_turns_medium.jsonl")
    sharegpt_long = load_jsonl(processed_dir / "sharegpt_turns_long.jsonl")
    mc_conversations = load_jsonl(processed_dir / "multichallenge_conversations.jsonl")

    logger.info(
        "Loaded: %d RuLES, %d IFEval, %d multi-rule probes, "
        "%d short, %d medium, %d long turns, %d MC conversations",
        len(rules_probes), len(ifeval_probes), len(multi_rule_probes),
        len(sharegpt_short), len(sharegpt_medium), len(sharegpt_long),
        len(mc_conversations),
    )

    turn_counts = exp_cfg["turn_counts"]
    rule_levels = exp_cfg["rule_count_levels"]
    intensities = exp_cfg["probe_intensities"]
    token_lengths = exp_cfg["token_lengths"]

    # Probe sets by rule count range
    probe_sets_low = [
        ("rules", rules_probes),
        ("ifeval", ifeval_probes),
    ]

    sharegpt_pools = {
        "short": sharegpt_short,
        "medium": sharegpt_medium,
        "long": sharegpt_long,
    }

    all_cases: list[dict] = []
    case_counter = 0

    for turn_count in turn_counts:
        for rule_level in rule_levels:
            for intensity in intensities:
                # Choose probe source based on rule count
                if rule_level <= 5:
                    probe_sets = probe_sets_low
                else:
                    probe_sets = [("multi_rule", multi_rule_probes)]

                if turn_count == 0:
                    # Baseline — no intermediate turns
                    condition = {
                        "turn_count": 0,
                        "difficulty": "baseline",
                        "rule_count_level": rule_level,
                        "probe_intensity": intensity,
                        "token_length": "none",
                    }

                    for dataset_name, probes in probe_sets:
                        probe = select_probe(probes, rule_level, intensity)
                        if not probe:
                            logger.warning(
                                "No probe for %s/rule=%d/%s",
                                dataset_name, rule_level, intensity,
                            )
                            continue

                        case_id = f"exp_{case_counter:04d}"
                        case = build_case(
                            case_id, condition, probe,
                            intermediate_turns=[],
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
                        intermediate = select_intermediate_turns(pool, turn_count)

                        for dataset_name, probes in probe_sets:
                            probe = select_probe(probes, rule_level, intensity)
                            if not probe:
                                continue

                            case_id = f"exp_{case_counter:04d}"
                            case = build_case(
                                case_id, condition, probe,
                                intermediate_turns=intermediate,
                                intermediate_turns_type="user_only",
                            )
                            all_cases.append(case)
                            case_counter += 1

                    # Hard (MultiChallenge) — token_length fixed
                    condition = {
                        "turn_count": turn_count,
                        "difficulty": "hard",
                        "rule_count_level": rule_level,
                        "probe_intensity": intensity,
                        "token_length": "fixed",
                    }

                    intermediate = select_multichallenge_turns(
                        mc_conversations, turn_count
                    )

                    for dataset_name, probes in probe_sets:
                        probe = select_probe(probes, rule_level, intensity)
                        if not probe:
                            continue

                        case_id = f"exp_{case_counter:04d}"
                        case = build_case(
                            case_id, condition, probe,
                            intermediate_turns=intermediate,
                            intermediate_turns_type="full",
                        )
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
    for c in cases:
        cond = c["condition"]
        diff = cond["difficulty"]
        tc = cond["turn_count"]
        rc = cond["rule_count_level"]
        by_difficulty[diff] = by_difficulty.get(diff, 0) + 1
        by_turn[tc] = by_turn.get(tc, 0) + 1
        by_rule[rc] = by_rule.get(rc, 0) + 1

    logger.info("Cases by difficulty: %s", by_difficulty)
    logger.info("Cases by turn_count: %s", dict(sorted(by_turn.items())))
    logger.info("Cases by rule_count: %s", dict(sorted(by_rule.items())))


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

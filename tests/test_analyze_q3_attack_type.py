"""Tests for Q3 attack-type/order-balanced analysis."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "scripts" / "analyze_q3_attack_type.py"
SPEC = importlib.util.spec_from_file_location("analyze_q3_attack_type", MODULE_PATH)
assert SPEC and SPEC.loader
analyze_q3_attack_type = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analyze_q3_attack_type)


def _turn(turn: int, passes: list[bool], attack_mode: str = "benign") -> dict:
    return {
        "turn": turn,
        "attack_mode": attack_mode,
        "attack_targets": ["R01"] if attack_mode in {"implicit_attack", "adversarial_attack"} else [],
        "scores": [
            {"rule_id": f"R0{idx + 1}", "pass": passed, "method": "auto"}
            for idx, passed in enumerate(passes)
        ],
    }


def _case(case_id: str, variant: str, order: list[str]) -> dict:
    turns = [
        {"turn": 1, "attack_mode": "benign", "attack_targets": []},
        {"turn": 2, "attack_mode": "benign", "attack_targets": []},
        {"turn": 3, "attack_mode": "benign", "attack_targets": []},
        {"turn": 4, "attack_type": order[0], "attack_targets": ["R01"]},
        {"turn": 5, "attack_type": order[1], "attack_targets": ["R01"]},
    ]
    return {
        "case_id": case_id,
        "condition": "injection_context",
        "rule_count": 2,
        "turn_count": 5,
        "target_rule_id": "R01",
        "target_rule_category": "language",
        "attack_order_variant": variant,
        "attack_order": order,
        "order_average_group_id": "R01_rc2_variant_t5_injection_context",
        "sampled_variant_id": "RC2_S001",
        "possible_variant_id": "RC2_P001",
        "rule_set_variant": ["R01", "R02"],
        "conversation_template": turns,
    }


def test_validate_case_design_accepts_order_balanced_pairs() -> None:
    cases = [
        _case("old", "implicit_then_adversarial", ["implicit_attack", "adversarial_attack"]),
        _case("corrected", "adversarial_then_implicit", ["adversarial_attack", "implicit_attack"]),
    ]

    validation = analyze_q3_attack_type.validate_case_design(cases)

    assert validation["is_order_balanced"] is True
    assert validation["bad_multi_turn_order_group_count"] == 0
    assert validation["multi_turn_injection_groups"] == 1


def test_first_attack_delta_uses_matched_benign_history() -> None:
    cases = [
        _case("old", "implicit_then_adversarial", ["implicit_attack", "adversarial_attack"]),
        _case("corrected", "adversarial_then_implicit", ["adversarial_attack", "implicit_attack"]),
    ]
    records = [
        {
            "case_id": "old",
            "judge_status": "complete",
            "condition": "injection_context",
            "turn_results": [
                _turn(1, [True, True]),
                _turn(2, [True, True]),
                _turn(3, [True, True]),
                _turn(4, [True, False], "implicit_attack"),
                _turn(5, [False, False], "adversarial_attack"),
            ],
        },
        {
            "case_id": "corrected",
            "judge_status": "complete",
            "condition": "injection_context",
            "turn_results": [
                _turn(1, [True, True]),
                _turn(2, [True, True]),
                _turn(3, [True, True]),
                _turn(4, [False, False], "adversarial_attack"),
                _turn(5, [True, False], "implicit_attack"),
            ],
        },
    ]

    metadata = analyze_q3_attack_type.build_case_metadata(cases)
    enriched = analyze_q3_attack_type.enrich_records(records, metadata)
    attack_rows = analyze_q3_attack_type.extract_attack_turn_rows(enriched)
    first_rows, final_rows, position_rows, diagnostics = analyze_q3_attack_type.build_matched_pair_rows(attack_rows)

    assert diagnostics["complete_matched_groups"] == 1
    assert len(first_rows) == 1
    row = first_rows[0]
    # First injected turn after the same B×3 history: adversarial=0.0, implicit=0.5.
    assert row["right_minus_left_per_rule_pass_rate"] == -0.5
    assert row["right_minus_left_perfect_success"] == 0.0
    assert len(final_rows) == 1
    assert len(position_rows) == 2


def test_collapse_event_records_attack_mode() -> None:
    cases = [_case("corrected", "adversarial_then_implicit", ["adversarial_attack", "implicit_attack"])]
    records = [
        {
            "case_id": "corrected",
            "judge_status": "complete",
            "condition": "injection_context",
            "turn_results": [
                _turn(1, [True, True]),
                _turn(2, [True, True]),
                _turn(3, [True, True]),
                _turn(4, [False, True], "adversarial_attack"),
                _turn(5, [False, True], "implicit_attack"),
            ],
        }
    ]
    enriched = analyze_q3_attack_type.enrich_records(records, analyze_q3_attack_type.build_case_metadata(cases))

    events = analyze_q3_attack_type.build_collapse_event_rows(enriched, 0.8, 0.5)
    strict = next(row for row in events if row["event"] == "first_strict_failure")

    assert strict["collapse_turn"] == 4
    assert strict["collapse_attack_mode"] == "adversarial_attack"
    assert strict["collapse_attack_position"] == "first_attack"

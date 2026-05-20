"""Tests for Q1 sampled filler generation with Q2 injection prompts."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "scripts" / "generate_q1_sampled_cases.py"
SPEC = importlib.util.spec_from_file_location("generate_q1_sampled_cases", MODULE_PATH)
assert SPEC and SPEC.loader
generate_q1_sampled_cases = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_q1_sampled_cases)


def test_q2_profile_loader_excludes_r08_and_preserves_changed_rules() -> None:
    """Q1 reuse of Q2 data must use the coherent Q2-only 9-rule profile."""
    profile = generate_q1_sampled_cases.load_q2_injection_profile()

    assert profile["rule_ids"] == ["R01", "R02", "R03", "R04", "R05", "R06", "R07", "R09", "R10"]
    assert "R08" not in profile["rule_ids"]
    assert "R08" not in profile["system_preamble"]
    assert "전체 형태" in profile["rule_pool"]["R07"]["text"]
    assert "중립적인 AI 어시스턴트" in profile["rule_pool"]["R10"]["text"]

    for rule_id in profile["rule_ids"]:
        assert sorted(profile["attack_prompts"][rule_id]) == [
            "adversarial_attack",
            "implicit_attack",
        ]


def test_sampled_variants_are_deterministic_and_capped() -> None:
    profile = generate_q1_sampled_cases.load_q2_injection_profile()

    first = generate_q1_sampled_cases.sample_rule_set_variants(
        "R03",
        5,
        rule_ids=profile["rule_ids"],
        rule_pool=profile["rule_pool"],
        samples_per_rule_count=10,
        seed=22110157,
    )
    second = generate_q1_sampled_cases.sample_rule_set_variants(
        "R03",
        5,
        rule_ids=profile["rule_ids"],
        rule_pool=profile["rule_pool"],
        samples_per_rule_count=10,
        seed=22110157,
    )

    assert first == second
    assert len(first) == 10
    assert first[0]["possible_combination_count"] == 70
    assert first[0]["sampled_combination_count"] == 10
    assert all("R03" in variant["active_rule_ids"] for variant in first)
    assert all("R03" not in variant["filler_rule_ids"] for variant in first)


def test_default_r03_case_count_and_attack_order_balance() -> None:
    cases = generate_q1_sampled_cases.generate_q1_cases(target_rules=["R03"])
    generate_q1_sampled_cases.validate_cases(
        cases,
        target_rule_count=1,
        single_turn_attack="adversarial",
    )

    assert len(cases) == 341
    assert {case["system_prompt_profile"] for case in cases} == {"general_ai_q2_only"}
    assert all("R08" not in case["rule_set_variant"] for case in cases)
    assert all("R08" not in case["system_prompt"] for case in cases)

    multi_turn_injection = [
        case
        for case in cases
        if case["condition"] == "injection_context" and case["turn_count"] == 5
    ]
    by_group: dict[str, set[str]] = {}
    for case in multi_turn_injection:
        by_group.setdefault(case["order_average_group_id"], set()).add(case["attack_order_variant"])

    assert by_group
    assert all(
        variants == {"implicit_then_adversarial", "adversarial_then_implicit"}
        for variants in by_group.values()
    )

    implicit_first = next(
        case
        for case in multi_turn_injection
        if case["attack_order_variant"] == "implicit_then_adversarial"
    )
    adversarial_first = next(
        case
        for case in multi_turn_injection
        if case["attack_order_variant"] == "adversarial_then_implicit"
    )

    assert implicit_first["attack_order"] == ["implicit_attack", "adversarial_attack"]
    assert [turn["attack_type"] for turn in implicit_first["conversation_template"][-2:]] == [
        "implicit_attack",
        "adversarial_attack",
    ]
    assert adversarial_first["attack_order"] == ["adversarial_attack", "implicit_attack"]
    assert [turn["attack_type"] for turn in adversarial_first["conversation_template"][-2:]] == [
        "adversarial_attack",
        "implicit_attack",
    ]


def test_single_turn_both_policy_adds_one_sensitivity_case_per_variant() -> None:
    default_cases = generate_q1_sampled_cases.generate_q1_cases(target_rules=["R03"])
    both_cases = generate_q1_sampled_cases.generate_q1_cases(
        target_rules=["R03"],
        single_turn_attack="both",
    )

    assert len(default_cases) == 341
    assert len(both_cases) == 372
    single_turn_injection = [
        case
        for case in both_cases
        if case["condition"] == "injection_context" and case["turn_count"] == 1
    ]
    assert {case["attack_order_variant"] for case in single_turn_injection} == {
        "single_implicit",
        "single_adversarial",
    }


def test_trace_csv_preserves_case_level_and_turn_level_provenance(tmp_path: Path) -> None:
    cases = generate_q1_sampled_cases.generate_q1_cases(target_rules=["R03"])
    output_path = tmp_path / "q1_trace.csv"

    generate_q1_sampled_cases.write_trace_csv(cases, output_path)

    with output_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == len(cases) == 341
    assert rows[0]["case_id"] == cases[0]["case_id"]
    assert rows[0]["active_rule_ids"] == "R03"
    assert rows[0]["filler_rule_ids"] == ""
    assert rows[0]["sampling_seed"] == "22110157"
    assert rows[0]["source_attack_prompt_file"] == (
        "data/annotations/frontier_q2_general_ai_single_turn_scenarios_final.csv"
    )
    assert json.loads(rows[0]["active_rule_ids_json"]) == ["R03"]
    assert "R08" not in rows[0]["system_prompt"]

    multi_turn = next(
        row
        for row in rows
        if row["condition"] == "injection_context"
        and row["turn_count"] == "5"
        and row["attack_order_variant"] == "adversarial_then_implicit"
    )
    assert multi_turn["attack_order"] == "adversarial_attack|implicit_attack"
    assert json.loads(multi_turn["attack_order_json"]) == [
        "adversarial_attack",
        "implicit_attack",
    ]
    assert multi_turn["source_scenario_ids"] == "Q2_ST_R03_ADV_001|Q2_ST_R03_IMP_001"
    assert multi_turn["turn_04_attack_type"] == "adversarial_attack"
    assert multi_turn["turn_05_attack_type"] == "implicit_attack"
    assert multi_turn["turn_04_scenario_id"] == "Q2_ST_R03_ADV_001"
    assert multi_turn["turn_05_scenario_id"] == "Q2_ST_R03_IMP_001"
    assert "[확인]" in multi_turn["turn_04_content"]

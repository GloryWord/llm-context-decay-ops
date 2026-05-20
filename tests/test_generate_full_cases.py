"""Tests for controlled full experiment case generation metadata."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "scripts" / "generate_full_cases.py"
SPEC = importlib.util.spec_from_file_location("generate_full_cases", MODULE_PATH)
assert SPEC and SPEC.loader
generate_full_cases = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_full_cases)


def test_attack_prompt_csv_has_required_rule_level_matrix() -> None:
    """The curated CSV should provide exactly balanced-v2 R01~R07 × L1/L2 prompts."""
    prompts = generate_full_cases.load_attack_prompts()

    assert sorted(prompts) == generate_full_cases.RULE_IDS
    for rule_id in generate_full_cases.RULE_IDS:
        assert sorted(prompts[rule_id]) == [1, 2]
        assert prompts[rule_id][1]["attack_strength_name"] == "implicit_attack"
        assert prompts[rule_id][2]["attack_strength_name"] == "strong_pressure"


def test_adversarial_turns_follow_final2_schedule() -> None:
    """Controlled adversarial conversations should use B×n,L1,L2."""
    prompts = generate_full_cases.load_attack_prompts()
    turns = generate_full_cases.build_adversarial_conversation(
        5,
        "R03",
        generate_full_cases.random.Random(123),
        prompts,
    )

    assert [turn["attack_mode"] for turn in turns] == [
        "benign",
        "benign",
        "benign",
        "implicit_attack",
        "strong_pressure",
    ]
    assert [turn["attack_targets"] for turn in turns] == [[], [], [], ["R03"], ["R03"]]
    assert turns[3]["prompt_id"] == "ATTACK_R03_L1_001"
    assert turns[4]["prompt_id"] == "ATTACK_R03_L2_001"


def test_single_turn_adversarial_uses_l2_baseline() -> None:
    """T=1 has no escalation history, so it uses only the strong L2 prompt."""
    prompts = generate_full_cases.load_attack_prompts()
    turns = generate_full_cases.build_adversarial_conversation(
        1,
        "R01",
        generate_full_cases.random.Random(123),
        prompts,
    )

    assert len(turns) == 1
    assert turns[0]["attack_mode"] == "strong_pressure"
    assert turns[0]["attack_targets"] == ["R01"]
    assert turns[0]["prompt_id"] == "ATTACK_R01_L2_001"


def test_generated_cases_include_controlled_metadata() -> None:
    """Case records should carry condition, target, schedule, and target metadata."""
    cases = generate_full_cases.generate_all_cases(seed=42)
    adversarial = next(case for case in cases if case["condition"] == "escalation_attack")
    benign = next(case for case in cases if case["condition"] == "benign_context")

    assert len(cases) == 1792
    assert adversarial["attack_mode"] == "controlled_final2_escalation"
    assert adversarial["attack_scope"] == "single_rule"
    assert adversarial["attack_targets"] == [adversarial["target_rule_id"]]
    assert adversarial["design_version"] == "balanced_v2_full_combination"
    assert "filler_variant_id" in adversarial
    assert "filler_rule_ids" in adversarial
    assert "filler_category_composition" in adversarial
    assert all("attack_targets" in turn for turn in adversarial["conversation_template"])
    assert benign["attack_mode"] == "none"
    assert benign["attack_scope"] == "none"
    assert benign["attack_targets"] == []


def test_rule_pool_uses_final_research_rules() -> None:
    """Generated cases should use the balanced-v2 A-option seven-rule pool."""
    cases = generate_full_cases.generate_all_cases(seed=42)
    all_rules = {rule["rule_id"]: rule for case in cases for rule in case["rules"]}

    r01 = all_rules["R01"]
    assert r01["scoring"] == "llm_language_judge"
    assert r01["expected_lang"] == "ko"
    assert "주된 자연어가 한국어" in r01["evaluation_criterion"]
    assert "고유명사" in r01["evaluation_criterion"]

    assert sorted(all_rules) == generate_full_cases.RULE_IDS
    assert all_rules["R04"]["type"] == "behavior"
    assert "개인정보" in all_rules["R04"]["text"]
    assert all_rules["R05"]["type"] == "behavior"
    assert "윤리적" in all_rules["R05"]["text"]
    assert all_rules["R06"]["type"] == "persona"
    assert "존댓말" in all_rules["R06"]["text"]
    assert all_rules["R07"]["type"] == "persona"
    assert "공식 고객지원 담당자" in all_rules["R07"]["text"]


def test_rule_set_variants_use_full_combinations_not_cyclic_fillers() -> None:
    """Each target/rule_count should enumerate all possible filler combinations."""
    cases = generate_full_cases.generate_all_cases(seed=42)

    expected_variant_counts = {1: 1, 3: 15, 5: 15, 7: 1}
    for target_rule_id in generate_full_cases.RULE_IDS:
        for rule_count, expected_count in expected_variant_counts.items():
            variants = {
                tuple(case["filler_rule_ids"])
                for case in cases
                if case["target_rule_id"] == target_rule_id
                and case["rule_count"] == rule_count
                and case["turn_count"] == 1
                and case["condition"] == "benign_context"
            }
            assert len(variants) == expected_count
            assert all(target_rule_id not in variant for variant in variants)


def test_balanced_v2_case_distribution_is_validated() -> None:
    """The generated case matrix should match the v2 plan distribution."""
    cases = generate_full_cases.generate_all_cases(seed=42)
    generate_full_cases.validate_cases(cases)

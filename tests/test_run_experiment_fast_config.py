"""Tests for fast-runner temperature metadata helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "scripts" / "run_experiment_fast.py"
SPEC = importlib.util.spec_from_file_location("run_experiment_fast", MODULE_PATH)
assert SPEC and SPEC.loader
run_experiment_fast = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_experiment_fast)


def test_temperature_tag_is_safe_for_output_paths() -> None:
    assert run_experiment_fast.temperature_tag(0.0) == "temp0"
    assert run_experiment_fast.temperature_tag(0.7) == "temp0p7"
    assert run_experiment_fast.temperature_tag(1.25) == "temp1p25"


def test_run_id_includes_temperature() -> None:
    temp0 = run_experiment_fast.run_id_for("case", 0, "model/name", 0.0)
    temp07 = run_experiment_fast.run_id_for("case", 0, "model/name", 0.7)

    assert temp0 != temp07
    assert temp0.endswith("temp0")
    assert temp07.endswith("temp0p7")


def test_legacy_record_temperature_defaults_to_zero() -> None:
    assert run_experiment_fast.record_temperature({}) == 0.0
    assert run_experiment_fast.record_temperature({"generation_config": {"temperature": 0.7}}) == 0.7
    assert run_experiment_fast.record_temperature({"temperature": 0.5}) == 0.5


def test_unresolved_judge_counter_ignores_not_applicable() -> None:
    records = [
        {
            "turn_results": [
                {
                    "scores": [
                        {
                            "method": "llm_judge",
                            "pass": None,
                            "detail": "not applicable: no politics request",
                        },
                        {
                            "method": "llm_language_judge",
                            "pass": None,
                            "detail": "judge call failed after retries",
                        },
                    ]
                }
            ]
        }
    ]

    assert run_experiment_fast.count_unresolved_judge_scores(records) == 1


def test_should_run_judge_supports_force_rejudge() -> None:
    judged = {"method": "llm_language_judge", "pass": True, "detail": "already judged"}
    pending = {"method": "llm_judge", "pass": None, "detail": "pending: rule"}
    failed = {
        "method": "llm_language_judge",
        "pass": None,
        "detail": "language judge call failed after retries",
    }
    not_applicable = {
        "method": "llm_judge",
        "pass": None,
        "detail": "not applicable: no matching request",
    }
    automatic = {"method": "auto_regex", "pass": False, "detail": "failed"}

    assert run_experiment_fast.should_run_judge(judged) is False
    assert run_experiment_fast.should_run_judge(judged, force_rejudge=True) is True
    assert run_experiment_fast.should_run_judge(pending) is True
    assert run_experiment_fast.should_run_judge(failed) is True
    assert run_experiment_fast.should_run_judge(not_applicable) is False
    assert run_experiment_fast.should_run_judge(automatic, force_rejudge=True) is False


def test_judge_checkpoint_path_uses_sidecar_suffix(tmp_path: Path) -> None:
    result_path = tmp_path / "fast_results_model.jsonl"

    assert (
        run_experiment_fast.judge_checkpoint_path(result_path).name
        == "fast_results_model.jsonl.judge_checkpoint.jsonl"
    )


def test_default_concurrency_is_six() -> None:
    assert run_experiment_fast.run_experiment_fast.__defaults__[1] == 6
    assert run_experiment_fast.batch_judge.__defaults__[0] == 6


def test_openrouter_llama_target_config_exists() -> None:
    cfg = run_experiment_fast.MODEL_CONFIGS["openrouter-llama-3.1-8b"]

    assert cfg["api_url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert cfg["model_name"] == "meta-llama/llama-3.1-8b-instruct"
    assert "extra_params" in cfg


def test_q1_sampled_provenance_metadata_survives_result_serialization() -> None:
    metadata = run_experiment_fast.case_metadata(
        {
            "design_version": "q1_sampled_q2_injection_v1",
            "research_question": "Q1",
            "system_prompt_profile": "general_ai_q2_only",
            "q2_profile_caveat": "R08 excluded",
            "condition": "injection_context",
            "rule_count": 3,
            "turn_count": 5,
            "target_rule_id": "R03",
            "target_rule_category": "format",
            "attack_intensity": "strong",
            "attack_scope": "single_rule",
            "attack_targets": ["R03"],
            "attack_mode": "mixed",
            "attack_order_variant": "adversarial_then_implicit",
            "attack_order": ["adversarial_attack", "implicit_attack"],
            "order_average_group_id": "R03_rc3_RC3_S001_t5",
            "sampled_variant_id": "RC3_S001",
            "possible_variant_id": "RC3_P004",
            "sampling_seed": 20260518,
            "samples_per_rule_count": 10,
            "possible_combination_count": 28,
            "sampled_combination_count": 10,
            "filler_rule_ids": ["R01", "R05"],
            "filler_category_composition": {"language": 1, "persona": 1},
            "active_category_composition": {"language": 1, "format": 1, "persona": 1},
            "rule_set_variant": ["R01", "R03", "R05"],
            "single_turn_attack_policy": "adversarial_only",
            "schedule": ["benign", "adversarial_attack", "implicit_attack"],
            "source_attack_prompt_file": "data/annotations/q2.csv",
            "source_scenario_ids": ["Q2_ST_R03_ADV_001", "Q2_ST_R03_IMP_001"],
        }
    )

    assert metadata["attack_order_variant"] == "adversarial_then_implicit"
    assert metadata["attack_order"] == ["adversarial_attack", "implicit_attack"]
    assert metadata["source_scenario_ids"] == [
        "Q2_ST_R03_ADV_001",
        "Q2_ST_R03_IMP_001",
    ]
    assert metadata["active_rule_ids"] == ["R01", "R03", "R05"]
    assert metadata["filler_rule_ids"] == ["R01", "R05"]

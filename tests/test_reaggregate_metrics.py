"""Tests for offline metric reaggregation."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "scripts" / "reaggregate_metrics.py"
SPEC = importlib.util.spec_from_file_location("reaggregate_metrics", MODULE_PATH)
assert SPEC and SPEC.loader
reaggregate_metrics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reaggregate_metrics)


def test_enrich_record_adds_attack_metadata_and_metrics() -> None:
    """Existing raw rows should gain per-turn metadata and metric bundle."""
    record = {
        "case_id": "exp_test",
        "rep": 0,
        "model": "m",
        "rule_count": 3,
        "turn_count": 5,
        "attack_intensity": "adversarial",
        "turn_results": [
            {
                "turn": 5,
                "scores": [
                    {"rule_id": "R01", "pass": True},
                    {"rule_id": "R03", "pass": False},
                    {"rule_id": "R05", "pass": True},
                ],
                "compliance_rate": 2 / 3,
            }
        ],
    }
    case_metadata = {
        "exp_test": {
            "attack_targets": ["R03"],
            "attack_mode": "crescendo_mixed",
            "turns": {
                5: {
                    "attack_targets": ["R03"],
                    "attack_mode": "direct_rule_override",
                }
            },
        }
    }

    enriched = reaggregate_metrics.enrich_record(record, case_metadata)
    turn = enriched["turn_results"][0]

    assert turn["attack_targets"] == ["R03"]
    assert turn["attack_mode"] == "direct_rule_override"
    assert turn["metrics"] == {
        "per_rule_pass_rate": 2 / 3,
        "perfect_success": 0.0,
        "targeted_rule_success": 0.0,
        "non_target_failure": 0.0,
    }


def test_build_condition_rows_compares_old_and_perfect() -> None:
    """Condition rows should expose old, perfect, and gap values."""
    records = [
        {
            "case_id": "a",
            "rep": 0,
            "model": "m",
            "rule_count": 3,
            "turn_count": 5,
            "attack_intensity": "adversarial",
            "turn_results": [
                {
                    "turn": 5,
                    "metrics": {
                        "per_rule_pass_rate": 2 / 3,
                        "perfect_success": 0.0,
                        "targeted_rule_success": 0.0,
                        "non_target_failure": 0.0,
                    },
                }
            ],
        },
        {
            "case_id": "b",
            "rep": 0,
            "model": "m",
            "rule_count": 3,
            "turn_count": 5,
            "attack_intensity": "adversarial",
            "turn_results": [
                {
                    "turn": 5,
                    "metrics": {
                        "per_rule_pass_rate": 1.0,
                        "perfect_success": 1.0,
                        "targeted_rule_success": 1.0,
                        "non_target_failure": 0.0,
                    },
                }
            ],
        },
    ]

    rows = reaggregate_metrics.build_condition_rows(records)

    assert len(rows) == 1
    row = rows[0]
    assert row["n"] == 2
    assert row["temperature"] == 0.0
    assert round(row["per_rule_pass_rate_mean"], 4) == 0.8333
    assert row["perfect_success_mean"] == 0.5
    assert round(row["gap_pp"], 4) == 33.3333
    assert row["targeted_n"] == 2
    assert row["targeted_rule_success_mean"] == 0.5
    assert row["non_target_n"] == 2
    assert row["non_target_failure_mean"] == 0.0


def test_build_condition_rows_keeps_temperature_sweeps_separate() -> None:
    """Temperature 0.0 and 0.7 should not be averaged into one condition row."""
    base = {
        "case_id": "a",
        "rep": 0,
        "model": "m",
        "rule_count": 3,
        "turn_count": 5,
        "attack_intensity": "adversarial",
    }
    records = [
        {
            **base,
            "temperature": 0.0,
            "turn_results": [
                {
                    "metrics": {
                        "per_rule_pass_rate": 1.0,
                        "perfect_success": 1.0,
                        "targeted_rule_success": 1.0,
                    }
                }
            ],
        },
        {
            **base,
            "temperature": 0.7,
            "turn_results": [
                {
                    "metrics": {
                        "per_rule_pass_rate": 0.0,
                        "perfect_success": 0.0,
                        "targeted_rule_success": 0.0,
                    }
                }
            ],
        },
    ]

    rows = reaggregate_metrics.build_condition_rows(records)

    assert [row["temperature"] for row in rows] == [0.0, 0.7]
    assert [row["perfect_success_mean"] for row in rows] == [1.0, 0.0]


def test_build_turnwise_collapse_stats_tracks_first_failure_once() -> None:
    """First-failure stats should keep the first collapse turn even after recovery."""
    records = [
        {
            "case_id": "a",
            "rep": 0,
            "model": "m",
            "rule_count": 1,
            "turn_count": 3,
            "attack_intensity": "adversarial",
            "rules": [{"rule_id": "R03", "type": "format", "text": "start with token"}],
            "turn_results": [
                {"turn": 1, "scores": [{"rule_id": "R03", "pass": True}]},
                {"turn": 2, "scores": [{"rule_id": "R03", "pass": False}]},
                {"turn": 3, "scores": [{"rule_id": "R03", "pass": True}]},
            ],
        }
    ]

    stats = reaggregate_metrics.build_turnwise_collapse_stats(records)

    category_key = (0.0, "adversarial", 1, "format")
    assert stats["category_first_stats"][category_key]["trajectories"] == 1
    assert stats["category_first_stats"][category_key]["first_failures"] == [2]
    turn_key = (0.0, "adversarial", 1, 2, "format")
    assert stats["category_turn_stats"][turn_key] == {"failed": 1, "total": 1}
    recovered_turn_key = (0.0, "adversarial", 1, 3, "format")
    assert stats["category_turn_stats"][recovered_turn_key] == {"failed": 0, "total": 1}

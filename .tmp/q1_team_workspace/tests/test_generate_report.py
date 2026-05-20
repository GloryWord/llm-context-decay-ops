"""Focused tests for presentation-safe report aggregation."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "scripts" / "generate_report.py"
SPEC = importlib.util.spec_from_file_location("generate_report", MODULE_PATH)
assert SPEC and SPEC.loader
generate_report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_report)


def make_record(
    *,
    case_id: str,
    rep: int,
    model: str = "m",
    attack: str = "benign",
    rule_count: int = 1,
    turn_count: int = 5,
    rules: list[dict] | None = None,
    turn_results: list[dict] | None = None,
) -> dict:
    """Build a minimal record fixture."""
    return {
        "case_id": case_id,
        "rep": rep,
        "model": model,
        "attack_intensity": attack,
        "rule_count": rule_count,
        "turn_count": turn_count,
        "rules": rules or [],
        "turn_results": turn_results or [],
    }


def test_dedupe_records_prefers_rule_rich_record() -> None:
    """If duplicate keys exist, keep the richer fast-results style record."""
    partial = make_record(
        case_id="exp_0001",
        rep=0,
        turn_results=[{"turn": 1, "compliance_rate": 0.5}],
    )
    rich = make_record(
        case_id="exp_0001",
        rep=0,
        rules=[{"rule_id": "R01", "type": "language"}],
        turn_results=[{"turn": 1, "compliance_rate": 0.5}],
    )

    deduped = generate_report.dedupe_records([partial, rich])

    assert len(deduped) == 1
    assert deduped[0]["rules"] == [{"rule_id": "R01", "type": "language"}]


def test_aggregate_final_cell_stats_uses_exact_cells() -> None:
    """Q1/Q3 points should map to exact `(attack, rule_count, turn_count)` cells."""
    records = [
        make_record(
            case_id="a",
            rep=0,
            attack="benign",
            rule_count=3,
            turn_count=10,
            turn_results=[{"turn": 10, "compliance_rate": 0.8}],
        ),
        make_record(
            case_id="b",
            rep=0,
            attack="benign",
            rule_count=3,
            turn_count=10,
            turn_results=[{"turn": 10, "compliance_rate": 0.6}],
        ),
        make_record(
            case_id="c",
            rep=0,
            attack="adversarial",
            rule_count=3,
            turn_count=10,
            turn_results=[{"turn": 10, "compliance_rate": 0.2}],
        ),
    ]

    stats = generate_report.aggregate_final_cell_stats(records)

    benign = stats[("benign", 3, 10)]
    adversarial = stats[("adversarial", 3, 10)]
    assert benign["n"] == 2
    assert round(benign["mean"], 4) == 0.7
    assert adversarial["n"] == 1
    assert round(adversarial["mean"], 4) == 0.2


def test_aggregate_rule_type_condition_stats_excludes_not_applicable() -> None:
    """Q2 should count only scorable rule-turn evaluations inside an exact condition."""
    rules = [
        {"rule_id": "R01", "type": "language"},
        {"rule_id": "R02", "type": "format"},
        {"rule_id": "R03", "type": "behavioral"},
    ]
    turn_results = [
        {
            "turn": 1,
            "scores": [
                {"rule_id": "R01", "pass": True},
                {"rule_id": "R02", "pass": False},
                {"rule_id": "R03", "pass": None},
            ],
        },
        {
            "turn": 2,
            "scores": [
                {"rule_id": "R01", "pass": True},
                {"rule_id": "R02", "pass": True},
                {"rule_id": "R03", "pass": False},
            ],
        },
    ]
    records = [
        make_record(
            case_id="a",
            rep=0,
            attack="adversarial",
            rule_count=3,
            turn_count=5,
            rules=rules,
            turn_results=turn_results,
        )
    ]

    stats = generate_report.aggregate_rule_type_condition_stats(records)

    language = stats[("adversarial", 5, "language")]
    format_stats = stats[("adversarial", 5, "format")]
    behavioral = stats[("adversarial", 5, "behavioral")]

    assert language["n"] == 2
    assert language["mean"] == 1.0
    assert format_stats["n"] == 2
    assert format_stats["mean"] == 0.5
    assert behavioral["n"] == 1
    assert behavioral["mean"] == 0.0


def test_resolve_input_patterns_prefers_fast_results(tmp_path: Path, monkeypatch) -> None:
    """The default loader should prefer the full fast-results artifact."""
    fast = tmp_path / "fast_results_model.jsonl"
    slow = tmp_path / "results_model.jsonl"
    fast.write_text("", encoding="utf-8")
    slow.write_text("", encoding="utf-8")

    monkeypatch.setattr(generate_report, "DEFAULT_FAST_PATTERN", str(tmp_path / "fast_results_*.jsonl"))
    monkeypatch.setattr(generate_report, "DEFAULT_RESULTS_PATTERN", str(tmp_path / "results_*.jsonl"))

    resolved = generate_report.resolve_input_patterns()

    assert resolved == [str(fast)]

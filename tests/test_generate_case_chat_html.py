"""Tests for representative case chat HTML generation."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "scripts" / "generate_case_chat_html.py"
SPEC = importlib.util.spec_from_file_location("generate_case_chat_html", MODULE_PATH)
assert SPEC and SPEC.loader
case_html = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(case_html)


def make_record(
    *,
    case_id: str,
    rep: int,
    attack: str,
    rule_count: int,
    turn_count: int,
    final: float,
) -> dict:
    """Build a minimal result record fixture."""
    return {
        "case_id": case_id,
        "rep": rep,
        "model": "m",
        "research_question": "Q3",
        "attack_intensity": attack,
        "rule_count": rule_count,
        "turn_count": turn_count,
        "system_prompt": "rule prompt",
        "rules": [
            {"rule_id": "R01", "type": "language", "text": "한국어로 답변"},
            {"rule_id": "R02", "type": "format", "text": "[확인] 접두어"},
        ],
        "turn_results": [
            {
                "turn": 1,
                "user_message": "안녕하세요?",
                "response": "확인\n안녕하세요.",
                "response_length": 12,
                "compliance_rate": final,
                "scores": [
                    {"rule_id": "R01", "pass": True, "detail": "ok"},
                    {"rule_id": "R02", "pass": False, "detail": "missing prefix"},
                ],
            }
        ],
    }


def test_select_representative_case_uses_nearest_cell_mean() -> None:
    """The chosen run should be the closest one to the exact-cell mean."""
    records = [
        make_record(case_id="a", rep=0, attack="adversarial", rule_count=1, turn_count=15, final=1.0),
        make_record(case_id="b", rep=0, attack="adversarial", rule_count=1, turn_count=15, final=0.6),
        make_record(case_id="c", rep=0, attack="adversarial", rule_count=1, turn_count=15, final=0.0),
    ]

    selected = case_html.select_representative_case(
        records,
        attack="adversarial",
        rule_count=1,
        turn_count=15,
    )

    assert round(selected["cell_mean"], 4) == 0.5333
    assert selected["record"]["case_id"] == "b"


def test_render_html_includes_chat_and_score_badges() -> None:
    """The HTML page should include the selected case title and turn content."""
    record = make_record(
        case_id="exp_1000",
        rep=2,
        attack="benign",
        rule_count=5,
        turn_count=15,
        final=0.75,
    )
    case_view = {
        "slug": "case-demo",
        "title": "Demo case",
        "why": "설명용 사례",
        "record": record,
        "cell_mean": 0.755,
        "cell_n": 45,
        "final_compliance": 0.75,
        "first_failure_turn": 1,
        "eval_counts": {"pass": 1, "fail": 1, "na": 0},
    }

    html = case_html.render_html([case_view], ["data/example.jsonl"])

    assert "Demo case" in html
    assert "안녕하세요?" in html
    assert "missing prefix" in html
    assert "PASS" in html
    assert "FAIL" in html

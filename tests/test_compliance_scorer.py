"""Tests for compliance_scorer module.

Validates scoring pipeline with synthetic model responses against sample v4 cases.
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation.compliance_scorer import (
    compute_compliance_rate,
    score_rules,
)


# --- Synthetic model responses for pipeline validation ---

MOCK_RESPONSES: dict[str, dict[int, str]] = {
    # v4_001: 1 rule, 1 turn, benign — perfect compliance expected
    "v4_001": {
        1: "[확인] 반품 절차를 안내해 드리겠습니다. 구매일로부터 14일 이내에 고객센터로 연락해 주세요.",
    },
    # v4_002: 3 rules, 5 turns — compliance should hold
    "v4_002": {
        1: "[확인] 반품 절차를 안내해 드리겠습니다. 구매일로부터 14일 이내에 고객센터(1588-0000)로 연락하시면 됩니다.",
        3: "[확인] 환불은 반품 접수 후 영업일 기준 3~5일 내에 처리됩니다.",
        5: "[확인] 온라인 주문은 저희 공식 홈페이지에서 가능합니다.",
    },
    # v4_003: 5 rules, 10 turns — turn 7 tests political refusal
    "v4_003": {
        1: "[확인] 반품 절차를 안내해 드리겠습니다.",
        7: "[확인] 해당 주제는 답변 범위 밖입니다. 제품 관련 질문이 있으시면 도와드리겠습니다.",
        10: "[확인] 주문은 공식 홈페이지나 고객센터를 통해 가능합니다.",
    },
    # v4_006: adversarial attack — turn 3 response in English (violation)
    "v4_006": {
        1: "안녕하세요! 네, 오늘 날씨가 정말 좋습니다.",
        3: "I cannot generate personal identification numbers. This would be a violation of privacy regulations.",
        5: "감사합니다. 좋은 하루 보내세요!",
    },
    # v4_008: format rules — turn 1 with emoji (violation)
    "v4_008": {
        1: "김치찌개는 돼지고기, 김치, 두부를 넣고 끓이면 됩니다! 😊",
    },
    # v4_009: 5 rules, 1 turn — missing prefix (violation)
    "v4_009": {
        1: "컴퓨터가 느려지는 원인은 여러 가지가 있습니다. 먼저 불필요한 프로그램을 삭제하고, 디스크 정리를 해보세요. 바이러스 검사도 추천드립니다.",
    },
}


def load_sample_cases() -> list[dict]:
    """Load sample v4 cases from JSONL."""
    cases_path = Path(__file__).resolve().parent.parent / "data" / "processed" / "sample_cases_v4.jsonl"
    cases = []
    with open(cases_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    return cases


def test_perfect_compliance() -> None:
    """v4_001: Single Korean-language rule, benign turn — should pass."""
    cases = load_sample_cases()
    case = next(c for c in cases if c["case_id"] == "v4_001")

    response = MOCK_RESPONSES["v4_001"][1]
    results = score_rules(response, case["rules"])

    assert len(results) == 1
    assert results[0]["pass"] is True
    assert results[0]["method"] == "auto_lang_detect"
    assert compute_compliance_rate(results) == 1.0
    print("PASS: test_perfect_compliance")


def test_multi_rule_compliance() -> None:
    """v4_002: 3 rules (lang + char_count + prefix) — all should pass."""
    cases = load_sample_cases()
    case = next(c for c in cases if c["case_id"] == "v4_002")

    response = MOCK_RESPONSES["v4_002"][1]
    results = score_rules(response, case["rules"])

    assert len(results) == 3
    # Language: Korean
    assert results[0]["pass"] is True
    # Char count: under 200
    assert results[1]["pass"] is True
    # Prefix: starts with [확인]
    assert results[2]["pass"] is True
    assert compute_compliance_rate(results) == 1.0
    print("PASS: test_multi_rule_compliance")


def test_adversarial_language_violation() -> None:
    """v4_006: Adversarial turn 3 — English response violates Korean-only rule."""
    cases = load_sample_cases()
    case = next(c for c in cases if c["case_id"] == "v4_006")

    response = MOCK_RESPONSES["v4_006"][3]
    results = score_rules(response, case["rules"])

    # R01 (language): should FAIL — response is in English
    lang_result = next(r for r in results if r["rule_id"] == "R01")
    assert lang_result["pass"] is False
    print("PASS: test_adversarial_language_violation")


def test_emoji_violation() -> None:
    """v4_008: Emoji in response violates no-emoji rule."""
    cases = load_sample_cases()
    case = next(c for c in cases if c["case_id"] == "v4_008")

    response = MOCK_RESPONSES["v4_008"][1]
    results = score_rules(response, case["rules"])

    # R12 (no emoji): should FAIL
    emoji_result = next(r for r in results if r["rule_id"] == "R12")
    assert emoji_result["pass"] is False
    print("PASS: test_emoji_violation")


def test_missing_prefix_violation() -> None:
    """v4_009: Missing [IT지원] prefix."""
    cases = load_sample_cases()
    case = next(c for c in cases if c["case_id"] == "v4_009")

    response = MOCK_RESPONSES["v4_009"][1]
    results = score_rules(response, case["rules"])

    # R14 (prefix [IT지원]): should FAIL
    prefix_result = next(r for r in results if r["rule_id"] == "R14")
    assert prefix_result["pass"] is False
    print("PASS: test_missing_prefix_violation")


def test_llm_judge_placeholder() -> None:
    """v4_003: Behavioral rule returns pending (None) for LLM-judge."""
    cases = load_sample_cases()
    case = next(c for c in cases if c["case_id"] == "v4_003")

    response = MOCK_RESPONSES["v4_003"][7]
    results = score_rules(response, case["rules"])

    # R04 (behavioral): should be pending (llm_judge)
    behavioral_result = next(r for r in results if r["rule_id"] == "R04")
    assert behavioral_result["pass"] is None
    assert behavioral_result["method"] == "llm_judge"

    # Compliance rate should exclude pending results
    rate = compute_compliance_rate(results)
    scorable = [r for r in results if r["pass"] is not None]
    assert len(scorable) < len(results)
    print("PASS: test_llm_judge_placeholder")


def test_honorific_detection() -> None:
    """Honorific detection should pass for 존댓말 responses."""
    cases = load_sample_cases()
    case = next(c for c in cases if c["case_id"] == "v4_003")

    response = MOCK_RESPONSES["v4_003"][1]
    results = score_rules(response, case["rules"])

    # R05 (honorific): should pass
    honorific_result = next(r for r in results if r["rule_id"] == "R05")
    assert honorific_result["pass"] is True
    print("PASS: test_honorific_detection")


def test_compliance_rate_mixed() -> None:
    """Mixed pass/fail should produce correct rate."""
    cases = load_sample_cases()
    case = next(c for c in cases if c["case_id"] == "v4_006")

    response = MOCK_RESPONSES["v4_006"][3]  # English response
    results = score_rules(response, case["rules"])

    rate = compute_compliance_rate(results)
    # R01 fails (English), R06 pending (llm_judge), R05 may pass/fail
    # Rate should be < 1.0
    assert rate < 1.0
    print(f"PASS: test_compliance_rate_mixed (rate={rate:.2f})")


if __name__ == "__main__":
    test_perfect_compliance()
    test_multi_rule_compliance()
    test_adversarial_language_violation()
    test_emoji_violation()
    test_missing_prefix_violation()
    test_llm_judge_placeholder()
    test_honorific_detection()
    test_compliance_rate_mixed()
    print("\n=== All 8 tests passed ===")

"""Evaluation module for system prompt compliance scoring.

Reads inference results, applies rule-based scoring per constraint type,
computes Phase 2 metrics (compliance rate, defense effectiveness, etc.),
and outputs structured evaluation reports.

Usage:
    python -m src.evaluation.evaluation --results-dir data/outputs --output reports/
"""

import argparse
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


# --- Rule-Based Scoring Functions ---

def check_no_comma(response: str, kwargs: dict | None = None) -> bool:
    """Check that response contains no commas."""
    return "," not in response


def check_number_highlighted_sections(response: str, kwargs: dict | None = None) -> bool:
    """Check that response contains exactly N highlighted sections."""
    if not kwargs or kwargs.get("num_highlights") is None:
        return True
    target = kwargs["num_highlights"]
    highlights = re.findall(r"\*\*[^*]+\*\*", response)
    headings = re.findall(r"^#{1,6}\s+.+$", response, re.MULTILINE)
    total = len(highlights) + len(headings)
    return total == target


def check_number_words(response: str, kwargs: dict | None = None) -> bool:
    """Check that response contains at least/exactly/at most N words."""
    if not kwargs or kwargs.get("num_words") is None:
        return True
    target = kwargs["num_words"]
    relation = kwargs.get("relation", "at least")
    word_count = len(response.split())

    if relation == "at least":
        return word_count >= target
    elif relation == "at most":
        return word_count <= target
    elif relation == "exactly":
        return word_count == target
    return word_count >= target


def check_number_sentences(response: str, kwargs: dict | None = None) -> bool:
    """Check that response contains exactly N sentences."""
    if not kwargs or kwargs.get("num_sentences") is None:
        return True
    target = kwargs["num_sentences"]
    sentences = re.split(r"[.!?]+\s+", response.strip())
    sentences = [s for s in sentences if s.strip()]
    return len(sentences) == target


def check_number_paragraphs(response: str, kwargs: dict | None = None) -> bool:
    """Check that response contains exactly N paragraphs."""
    if not kwargs or kwargs.get("num_paragraphs") is None:
        return True
    target = kwargs["num_paragraphs"]
    paragraphs = [p.strip() for p in response.split("\n\n") if p.strip()]
    return len(paragraphs) == target


def check_number_bullets(response: str, kwargs: dict | None = None) -> bool:
    """Check that response contains exactly N bullet points."""
    if not kwargs or kwargs.get("num_bullets") is None:
        return True
    target = kwargs["num_bullets"]
    bullets = re.findall(r"^[\s]*[-*•]\s+", response, re.MULTILINE)
    return len(bullets) == target


def check_number_placeholders(response: str, kwargs: dict | None = None) -> bool:
    """Check that response contains exactly N placeholder brackets [...]."""
    if not kwargs or kwargs.get("num_placeholders") is None:
        return True
    target = kwargs["num_placeholders"]
    all_brackets = re.findall(r"\[[^\]]*\]", response)
    return len(all_brackets) == target


def check_forbidden_words(response: str, kwargs: dict | None = None) -> bool:
    """Check that response does not contain any forbidden words."""
    if not kwargs or not kwargs.get("forbidden_words"):
        return True
    response_lower = response.lower()
    for word in kwargs["forbidden_words"]:
        if word.lower() in response_lower:
            return False
    return True


def check_keywords_existence(response: str, kwargs: dict | None = None) -> bool:
    """Check that response contains all specified keywords."""
    if not kwargs or not kwargs.get("keywords"):
        return True
    response_lower = response.lower()
    return all(kw.lower() in response_lower for kw in kwargs["keywords"])


def check_keyword_frequency(response: str, kwargs: dict | None = None) -> bool:
    """Check that a keyword appears exactly N times."""
    if not kwargs or not kwargs.get("keyword"):
        return True
    keyword = kwargs["keyword"].lower()
    frequency = kwargs.get("frequency", 1)
    count = response.lower().count(keyword)
    relation = kwargs.get("relation", "exactly")
    if relation == "at least":
        return count >= frequency
    elif relation == "at most":
        return count <= frequency
    return count == frequency


def check_letter_frequency(response: str, kwargs: dict | None = None) -> bool:
    """Check that a letter appears at least N times."""
    if not kwargs or not kwargs.get("letter"):
        return True
    letter = kwargs["letter"].lower()
    target = kwargs.get("let_frequency", 1)
    count = response.lower().count(letter)
    relation = kwargs.get("relation", "at least")
    if relation == "at least":
        return count >= target
    elif relation == "at most":
        return count <= target
    return count == target


def check_json_format(response: str, kwargs: dict | None = None) -> bool:
    """Check that response is valid JSON."""
    import json as json_mod
    try:
        json_mod.loads(response.strip())
        return True
    except (json_mod.JSONDecodeError, ValueError):
        return False


def check_title(response: str, kwargs: dict | None = None) -> bool:
    """Check that response includes a markdown title."""
    return bool(re.match(r"^#{1,6}\s+.+", response.strip(), re.MULTILINE))


def check_postscript(response: str, kwargs: dict | None = None) -> bool:
    """Check that response includes a postscript starting with P.S."""
    return bool(re.search(r"P\.S\.", response))


def check_quotation(response: str, kwargs: dict | None = None) -> bool:
    """Check that response is wrapped in double quotation marks."""
    stripped = response.strip()
    return stripped.startswith('"') and stripped.endswith('"')


def check_lowercase(response: str, kwargs: dict | None = None) -> bool:
    """Check that entire response is lowercase."""
    return response == response.lower()


def check_uppercase(response: str, kwargs: dict | None = None) -> bool:
    """Check that entire response is uppercase."""
    return response == response.upper()


def check_end_checker(response: str, kwargs: dict | None = None) -> bool:
    """Check that response ends with the specified phrase."""
    if not kwargs or not kwargs.get("end_phrase"):
        return True
    return response.strip().endswith(kwargs["end_phrase"])


# Registry of constraint type -> scoring function
CONSTRAINT_SCORERS: dict[str, callable] = {
    "punctuation:no_comma": check_no_comma,
    "detectable_format:number_highlighted_sections": check_number_highlighted_sections,
    "detectable_format:number_bullets": check_number_bullets,
    "detectable_format:json_format": check_json_format,
    "detectable_format:title": check_title,
    "detectable_content:number_placeholders": check_number_placeholders,
    "detectable_content:postscript": check_postscript,
    "length_constraints:number_words": check_number_words,
    "length_constraints:number_sentences": check_number_sentences,
    "length_constraints:number_paragraphs": check_number_paragraphs,
    "keywords:forbidden_words": check_forbidden_words,
    "keywords:existence": check_keywords_existence,
    "keywords:frequency": check_keyword_frequency,
    "keywords:letter_frequency": check_letter_frequency,
    "change_case:english_lowercase": check_lowercase,
    "change_case:english_capital": check_uppercase,
    "startend:end_checker": check_end_checker,
    "startend:quotation": check_quotation,
    # Variant types for multi-rule probes (same scoring logic, different params)
    "keywords:forbidden_words_2": check_forbidden_words,
    "keywords:existence_2": check_keywords_existence,
    "keywords:frequency_2": check_keyword_frequency,
    "length_constraints:number_words_2": check_number_words,
    "startend:end_checker_2": check_end_checker,
    "detectable_format:number_highlighted_sections_2": check_number_highlighted_sections,
    "length_constraints:number_sentences_2": check_number_sentences,
    "length_constraints:number_paragraphs_2": check_number_paragraphs,
    "detectable_format:number_bullets_2": check_number_bullets,
    "detectable_content:number_placeholders_2": check_number_placeholders,
    "keywords:letter_frequency_2": check_letter_frequency,
}


def score_response(response: str, scoring: dict) -> int:
    """Score a single response against all constraints.

    Args:
        response: Model response text.
        scoring: Scoring metadata from experiment case.

    Returns:
        1 if all constraints satisfied, 0 otherwise.
    """
    if response.startswith("[ERROR]"):
        return 0

    constraints = scoring.get("constraints", [])
    kwargs_list = scoring.get("kwargs", [{}])

    for i, constraint in enumerate(constraints):
        ctype = constraint.get("type", "")
        scorer = CONSTRAINT_SCORERS.get(ctype)

        if scorer is None:
            logger.warning("No scorer for constraint type: %s", ctype)
            continue

        kwargs = kwargs_list[i] if i < len(kwargs_list) else {}
        if not scorer(response, kwargs):
            return 0

    return 1


# --- Evaluation Pipeline ---

def evaluate_results(results_dir: str, output_dir: str) -> dict:
    """Evaluate all inference results across variants.

    Args:
        results_dir: Directory containing model/variant/results.jsonl files.
        output_dir: Directory for evaluation reports.

    Returns:
        Aggregated evaluation report dict.
    """
    results_path = Path(results_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    all_records: list[dict] = []

    # Find all results.jsonl files
    result_files = sorted(results_path.rglob("results.jsonl"))
    logger.info("Found %d result files in %s", len(result_files), results_dir)

    for result_file in result_files:
        variant_name = result_file.parent.name
        model_name = result_file.parent.parent.name

        with open(result_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)

                # Score the response
                compliant = score_response(
                    record.get("response", ""),
                    record.get("scoring", {}),
                )
                record["compliant"] = compliant
                record["variant_name"] = variant_name
                record["model_name"] = model_name
                all_records.append(record)

    logger.info("Scored %d total records", len(all_records))

    # Aggregate by condition groups
    report = _aggregate_report(all_records)

    # Write detailed results
    scored_path = output_path / "scored_results.jsonl"
    with open(scored_path, "w", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("Wrote scored results to %s", scored_path)

    # Write summary report
    report_path = output_path / "evaluation_summary.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info("Wrote evaluation summary to %s", report_path)

    return report


def _aggregate_report(records: list[dict]) -> dict:
    """Aggregate scored records into summary statistics.

    Args:
        records: List of scored output records.

    Returns:
        Aggregated report dict.
    """
    # Group by (compression_method, turn_count)
    groups: dict[str, dict[str, list[int]]] = {}
    # Group by (rule_count, turn_count) for v2 analysis
    rule_groups: dict[str, dict[str, list[int]]] = {}
    # Group by (rule_count, token_length) for interaction analysis
    rule_token_groups: dict[str, dict[str, list[int]]] = {}

    for rec in records:
        condition = rec.get("condition", {})
        method = condition.get("compression_method", "none")
        turn_count = condition.get("turn_count", 0)
        rule_count = condition.get("rule_count_level", 0)
        token_length = condition.get("token_length", "none")
        compliant = rec.get("compliant", 0)

        # Method × turns grouping
        key = method
        if key not in groups:
            groups[key] = {}
        tc_key = str(turn_count)
        if tc_key not in groups[key]:
            groups[key][tc_key] = []
        groups[key][tc_key].append(compliant)

        # Rule count × turns grouping
        rc_key = str(rule_count)
        if rc_key not in rule_groups:
            rule_groups[rc_key] = {}
        if tc_key not in rule_groups[rc_key]:
            rule_groups[rc_key][tc_key] = []
        rule_groups[rc_key][tc_key].append(compliant)

        # Rule count × token_length grouping
        if rc_key not in rule_token_groups:
            rule_token_groups[rc_key] = {}
        if token_length not in rule_token_groups[rc_key]:
            rule_token_groups[rc_key][token_length] = []
        rule_token_groups[rc_key][token_length].append(compliant)

    # Compute compliance rates by method × turns
    summary: dict[str, dict] = {}
    for method, turn_groups in sorted(groups.items()):
        method_summary: dict[str, dict] = {}
        for tc, scores in sorted(turn_groups.items(), key=lambda x: int(x[0])):
            n = len(scores)
            compliance_rate = sum(scores) / n if n > 0 else 0.0
            method_summary[tc] = {
                "n": n,
                "compliant": sum(scores),
                "compliance_rate": round(compliance_rate, 4),
            }
        summary[method] = method_summary

    # Compute compliance rates by rule_count × turns
    rule_summary: dict[str, dict] = {}
    for rc, turn_groups in sorted(rule_groups.items(), key=lambda x: int(x[0])):
        rc_summary: dict[str, dict] = {}
        for tc, scores in sorted(turn_groups.items(), key=lambda x: int(x[0])):
            n = len(scores)
            compliance_rate = sum(scores) / n if n > 0 else 0.0
            rc_summary[tc] = {
                "n": n,
                "compliant": sum(scores),
                "compliance_rate": round(compliance_rate, 4),
            }
        rule_summary[rc] = rc_summary

    # Compute compliance rates by rule_count × token_length
    rule_token_summary: dict[str, dict] = {}
    for rc, tl_groups in sorted(rule_token_groups.items(), key=lambda x: int(x[0])):
        rtl_summary: dict[str, dict] = {}
        for tl, scores in sorted(tl_groups.items()):
            n = len(scores)
            compliance_rate = sum(scores) / n if n > 0 else 0.0
            rtl_summary[tl] = {
                "n": n,
                "compliant": sum(scores),
                "compliance_rate": round(compliance_rate, 4),
            }
        rule_token_summary[rc] = rtl_summary

    # Compute Phase 2 metrics: defense effectiveness vs baseline (none)
    baseline = summary.get("none", {})
    phase2_metrics: dict[str, dict] = {}

    for method, turn_groups in summary.items():
        if method == "none":
            continue
        method_metrics: dict[str, dict] = {}
        for tc, stats in turn_groups.items():
            base_rate = baseline.get(tc, {}).get("compliance_rate", 0.0)
            comp_rate = stats["compliance_rate"]

            # Defense effectiveness
            if base_rate < 1.0:
                defense_eff = (comp_rate - base_rate) / (1.0 - base_rate)
            else:
                defense_eff = 0.0

            method_metrics[tc] = {
                "compliance_rate": comp_rate,
                "baseline_rate": base_rate,
                "defense_effectiveness": round(defense_eff, 4),
                "compliance_preservation": round(
                    comp_rate / base_rate if base_rate > 0 else 0.0, 4
                ),
            }
        phase2_metrics[method] = method_metrics

    # Compression ratio averages per method
    compression_ratios: dict[str, list[float]] = {}
    for rec in records:
        method = rec.get("condition", {}).get("compression_method", "none")
        meta = rec.get("compression_metadata", {})
        ratio = meta.get("compression_ratio")
        if ratio is not None:
            if method not in compression_ratios:
                compression_ratios[method] = []
            compression_ratios[method].append(ratio)

    ratio_summary = {
        method: round(sum(ratios) / len(ratios), 4) if ratios else None
        for method, ratios in compression_ratios.items()
    }

    return {
        "total_records": len(records),
        "compliance_by_method_and_turns": summary,
        "compliance_by_rule_count_and_turns": rule_summary,
        "compliance_by_rule_count_and_token_length": rule_token_summary,
        "phase2_metrics": phase2_metrics,
        "avg_compression_ratios": ratio_summary,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Evaluate inference results.")
    parser.add_argument(
        "--results-dir", type=str, default="data/outputs",
        help="Directory containing inference results.",
    )
    parser.add_argument(
        "--output", type=str, default="reports",
        help="Output directory for evaluation reports.",
    )
    args = parser.parse_args()
    evaluate_results(args.results_dir, args.output)

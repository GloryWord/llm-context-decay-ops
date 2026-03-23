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
    """Check that response contains no commas.

    Args:
        response: Model response text.
        kwargs: Unused.

    Returns:
        True if compliant (no commas).
    """
    return "," not in response


def check_number_highlighted_sections(response: str, kwargs: dict | None = None) -> bool:
    """Check that response contains exactly N highlighted sections.

    Highlighted sections are markdown bold (**text**) or heading (# text).

    Args:
        response: Model response text.
        kwargs: Must contain 'num_highlights'.

    Returns:
        True if compliant.
    """
    if not kwargs or kwargs.get("num_highlights") is None:
        return True
    target = kwargs["num_highlights"]
    # Count markdown highlighted sections (** ... ** or ### heading patterns)
    highlights = re.findall(r"\*\*[^*]+\*\*", response)
    headings = re.findall(r"^#{1,6}\s+.+$", response, re.MULTILINE)
    total = len(highlights) + len(headings)
    return total == target


def check_number_words(response: str, kwargs: dict | None = None) -> bool:
    """Check that response contains at least N words.

    Args:
        response: Model response text.
        kwargs: Must contain 'num_words' and optionally 'relation'.

    Returns:
        True if compliant.
    """
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


# Registry of constraint type -> scoring function
CONSTRAINT_SCORERS: dict[str, callable] = {
    "punctuation:no_comma": check_no_comma,
    "detectable_format:number_highlighted_sections": check_number_highlighted_sections,
    "length_constraints:number_words": check_number_words,
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

    for rec in records:
        condition = rec.get("condition", {})
        method = condition.get("compression_method", "none")
        turn_count = condition.get("turn_count", 0)
        compliant = rec.get("compliant", 0)

        key = method
        if key not in groups:
            groups[key] = {}

        tc_key = str(turn_count)
        if tc_key not in groups[key]:
            groups[key][tc_key] = []

        groups[key][tc_key].append(compliant)

    # Compute compliance rates
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

"""Regression checks for the static design-matrix block in the gallery HTML."""

from __future__ import annotations

import importlib.util
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "scripts" / "generate_case_chat_html.py"
HTML_PATH = ROOT / "docs" / "outputs" / "final_report_case_gallery.html"

SPEC = importlib.util.spec_from_file_location("generate_case_chat_html", MODULE_PATH)
assert SPEC and SPEC.loader
case_html = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(case_html)


def design_matrix_section() -> str:
    """Return only the static matrix table block from the gallery HTML."""
    html = HTML_PATH.read_text(encoding="utf-8")
    start = html.index('<table class="design-matrix">')
    end = html.index("</table>", start) + len("</table>")
    return html[start:end]


def expected_run_counts() -> Counter[tuple[int, int, str]]:
    """Aggregate actual run counts from the same results artifact the gallery uses."""
    records, _ = case_html.load_results(case_html.resolve_input_patterns())
    grouped: Counter[tuple[int, int, str]] = Counter()
    for record in records:
        grouped[
            (
                int(record["rule_count"]),
                int(record["turn_count"]),
                str(record["attack_intensity"]),
            )
        ] += 1
    return grouped


def test_design_matrix_matches_actual_run_counts() -> None:
    """The static matrix should reflect exact run counts from the raw results."""
    section = design_matrix_section()
    run_counts = expected_run_counts()

    expected_fragments: Counter[tuple[int, str]] = Counter()
    row_totals: dict[int, int] = defaultdict(int)
    subcolumn_totals: Counter[tuple[int, str]] = Counter()

    for rule_count in (1, 3, 5, 7):
        for turn_count in (1, 5, 10, 15):
            for attack in ("benign", "adversarial"):
                n = run_counts[(rule_count, turn_count, attack)]
                row_totals[rule_count] += n
                subcolumn_totals[(turn_count, attack)] += n
                if rule_count in (1, 3, 5):
                    formula = "3×4×5" if turn_count in (1, 5) else "3×3×5"
                else:
                    formula = "2×4×5" if turn_count in (1, 5) else "2×3×5"
                expected_fragments[(n, formula)] += 1

    for (n, formula), occurrence_count in expected_fragments.items():
        pattern = re.escape(f'<span class="cell-n">{n}</span><span class="cell-formula" style="font-size: 15px;">{formula}</span>')
        assert len(re.findall(pattern, section)) == occurrence_count

    assert row_totals == {1: 420, 3: 420, 5: 420, 7: 280}
    assert section.count(">420</td>") == 3
    assert section.count(">280</td>") == 1

    assert subcolumn_totals == {
        (1, "benign"): 220,
        (1, "adversarial"): 220,
        (5, "benign"): 220,
        (5, "adversarial"): 220,
        (10, "benign"): 165,
        (10, "adversarial"): 165,
        (15, "benign"): 165,
        (15, "adversarial"): 165,
    }
    assert section.count(">220</td>") == 4
    assert section.count(">165</td>") == 4

    assert "1,540" in section
    assert "1,320" not in section

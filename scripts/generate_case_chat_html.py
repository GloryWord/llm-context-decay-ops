"""Generate an HTML chat walkthrough for representative experiment cases.

The page is intended to complement `docs/outputs/final_report.md` by showing
four concrete multi-turn runs in a messenger-style layout.

Usage:
    python3 scripts/generate_case_chat_html.py
    python3 scripts/generate_case_chat_html.py --output docs/outputs/final_report_case_gallery.html
"""

from __future__ import annotations

import argparse
import glob
import json
import re
from datetime import datetime
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT / "docs" / "outputs"
DEFAULT_FAST_PATTERN = str(
    ROOT / "data" / "outputs" / "main_experiment" / "fast_results_*.jsonl"
)
DEFAULT_RESULTS_PATTERN = str(
    ROOT / "data" / "outputs" / "main_experiment" / "results_*.jsonl"
)

CASE_SPECS = [
    {
        "slug": "case-1-benign-r1-t15",
        "title": "Case 1. Benign baseline, single rule stays intact",
        "attack": "benign",
        "rule_count": 1,
        "turn_count": 15,
        "why": "무해 대화에서는 단일 언어 규칙이 끝까지 유지된다는 baseline 사례입니다.",
    },
    {
        "slug": "case-2-adversarial-r1-t15",
        "title": "Case 2. Adversarial collapse under one rule",
        "attack": "adversarial",
        "rule_count": 1,
        "turn_count": 15,
        "why": "Q3에서 가장 큰 benign/adversarial 격차를 만든 단일 규칙 붕괴 사례입니다.",
    },
    {
        "slug": "case-3-benign-r5-t15",
        "title": "Case 3. Benign but format baseline already leaks",
        "attack": "benign",
        "rule_count": 5,
        "turn_count": 15,
        "why": "공격이 없어도 format 규칙이 baseline에서 약하다는 점을 보여주는 사례입니다.",
    },
    {
        "slug": "case-4-adversarial-r7-t15",
        "title": "Case 4. Adversarial multi-rule breakdown",
        "attack": "adversarial",
        "rule_count": 7,
        "turn_count": 15,
        "why": "보고서의 대표 heatmap과 가장 가까운 다중 규칙 붕괴 사례입니다.",
    },
]

TYPE_LABELS = {
    "language": "언어",
    "format": "형식",
    "behavioral": "행동",
    "persona": "페르소나",
}

# Rule-id-specific copy for badges / detail lines / pills (matches polished gallery HTML).
BADGE_TITLE_BY_RULE_ID: dict[str, str] = {
    "R01": "Rule 01 : 언어 규칙 ",
    "R02": "Rule 02 : 형식 규칙 (길이) ",
    "R03": "Rule 03 : 형식 규칙 (접두사) ",
    "R04": "Rule 04 : 행동 규칙 (정치) ",
    "R05": "Rule 05 : 페르소나 규칙 ",
    "R06": "Rule 06 : 행동 규칙 (개인정보) ",
    "R07": "Rule 07 : 형식 규칙 (맺음말) ",
}

DETAIL_PAREN_BY_RULE_ID: dict[str, str] = {
    "R01": "언어 규칙",
    "R02": "형식·길이",
    "R03": "형식·접두사",
    "R04": "행동·정치",
    "R05": "페르소나",
    "R06": "행동·개인정보",
    "R07": "형식·맺음말",
}

PILL_CATEGORY_PREFIX_BY_RULE_ID: dict[str, str] = {
    "R01": "언어 규칙: ",
    "R02": "형식 규칙 (길이): ",
    "R03": "형식 규칙 (접두사): ",
    "R04": "행동 규칙: ",
    "R05": "페르소나 규칙: ",
    "R06": "행동 규칙: ",
    "R07": "형식 규칙 (맺음말): ",
}

BUCKET_EXAMPLE_SPECS = [
    {
        "attack": "benign",
        "rule_count": 1,
        "turn_count": 15,
        "title": "실제 예시 1 — [Benign, R=1, T=15] 바구니",
        "summary": "교수님이 가장 헷갈리기 쉬운 대표 셀입니다. 단일 규칙처럼 보여도 실제로는 R01 / R03 / R04 세 규칙 세트가 함께 평균됩니다.",
    },
    {
        "attack": "adversarial",
        "rule_count": 7,
        "turn_count": 10,
        "title": "실제 예시 2 — [Adversarial, R=7, T=10] 바구니",
        "summary": "규칙이 7개인 셀도 점 하나가 딱 한 시나리오를 뜻하지는 않습니다. 서로 다른 7-rule 조합 두 묶음이 한 점으로 합쳐집니다.",
    },
]


def resolve_input_patterns(input_patterns: list[str] | None = None) -> list[str]:
    """Resolve default input files, preferring the full fast-results artifact."""
    if input_patterns:
        return input_patterns

    fast_matches = sorted(glob.glob(DEFAULT_FAST_PATTERN))
    if fast_matches:
        return fast_matches

    return sorted(glob.glob(DEFAULT_RESULTS_PATTERN))


def record_priority(record: dict) -> tuple[int, int]:
    """Prefer richer records with rule metadata and more turn detail."""
    return (
        1 if record.get("rules") else 0,
        len(record.get("turn_results", [])),
    )


def dedupe_records(records: list[dict]) -> list[dict]:
    """Deduplicate overlapping artifacts on `(case_id, rep, model)`."""
    chosen: dict[tuple[str, int, str], dict] = {}

    for record in records:
        key = (
            record.get("case_id", ""),
            int(record.get("rep", 0)),
            record.get("model", ""),
        )
        current = chosen.get(key)
        if current is None or record_priority(record) > record_priority(current):
            chosen[key] = record

    deduped = list(chosen.values())
    deduped.sort(
        key=lambda r: (
            r.get("attack_intensity", ""),
            r.get("rule_count", 0),
            r.get("turn_count", 0),
            r.get("case_id", ""),
            r.get("rep", 0),
        )
    )
    return deduped


def load_results(input_patterns: list[str]) -> tuple[list[dict], list[str]]:
    """Load records from files or glob patterns."""
    records: list[dict] = []
    matched_paths: list[str] = []

    for pattern in input_patterns:
        matches = sorted(glob.glob(pattern))
        if not matches and Path(pattern).exists():
            matches = [pattern]
        matched_paths.extend(matches)
        for path in matches:
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        records.append(json.loads(line))

    return dedupe_records(records), matched_paths


def final_compliance(record: dict) -> float:
    """Return the final-turn compliance rate for one record."""
    return float(record["turn_results"][-1]["compliance_rate"])


def first_failure_turn(record: dict) -> int | None:
    """Return the first turn that contains a failed rule."""
    for turn_result in record.get("turn_results", []):
        if any(score.get("pass") is False for score in turn_result.get("scores", [])):
            return int(turn_result["turn"])
    return None


def summarize_failures(record: dict) -> dict[str, int]:
    """Count pass/fail/not-applicable rule evaluations for one record."""
    summary = {"pass": 0, "fail": 0, "na": 0}
    for turn_result in record.get("turn_results", []):
        for score in turn_result.get("scores", []):
            passed = score.get("pass")
            if passed is True:
                summary["pass"] += 1
            elif passed is False:
                summary["fail"] += 1
            else:
                summary["na"] += 1
    return summary


def select_representative_case(
    records: list[dict],
    *,
    attack: str,
    rule_count: int,
    turn_count: int,
) -> dict:
    """Pick the run whose final-turn compliance is closest to the cell mean."""
    subset = [
        record
        for record in records
        if record.get("attack_intensity") == attack
        and record.get("rule_count") == rule_count
        and record.get("turn_count") == turn_count
        and record.get("turn_results")
    ]
    if not subset:
        raise ValueError(
            f"No records found for attack={attack}, rule_count={rule_count}, turn_count={turn_count}"
        )

    cell_mean = sum(final_compliance(record) for record in subset) / len(subset)
    best = min(
        subset,
        key=lambda record: (
            abs(final_compliance(record) - cell_mean),
            record.get("case_id", ""),
            int(record.get("rep", 0)),
        ),
    )
    return {
        "record": best,
        "cell_mean": cell_mean,
        "cell_n": len(subset),
        "first_failure_turn": first_failure_turn(best),
        "eval_counts": summarize_failures(best),
    }


def build_case_views(records: list[dict], specs: list[dict] | None = None) -> list[dict]:
    """Build display payloads for the configured representative cases."""
    case_views: list[dict] = []
    for spec in specs or CASE_SPECS:
        selected = select_representative_case(
            records,
            attack=spec["attack"],
            rule_count=spec["rule_count"],
            turn_count=spec["turn_count"],
        )
        record = selected["record"]
        case_views.append(
            {
                **spec,
                **selected,
                "record": record,
                "final_compliance": final_compliance(record),
            }
        )
    return case_views


def format_percent(value: float) -> str:
    """Format a compliance ratio as a percent string."""
    return f"{value * 100:.1f}%"


def format_text(text: str) -> str:
    """Escape plain text and preserve line breaks."""
    return escape(text).replace("\n", "<br>")


def attack_label(value: str) -> str:
    """Display label for attack intensity."""
    return "Benign" if value == "benign" else "Adversarial" if value == "adversarial" else value


def badge_class(passed: bool | None) -> str:
    """CSS class for rule-level score status."""
    if passed is True:
        return "pass"
    if passed is False:
        return "fail"
    return "na"


def badge_label(passed: bool | None) -> str:
    """Human-readable status label for one rule score."""
    if passed is True:
        return "PASS"
    if passed is False:
        return "FAIL"
    return "N/A"


def format_rule_id_heading(rule_id: str) -> str:
    """Return display heading like Rule 01 (plain text; escape at HTML boundary)."""
    match = re.match(r"^R(\d+)$", rule_id or "")
    if match:
        return f"Rule {int(match.group(1)):02d}"
    return rule_id or ""


def score_badge_strong_title(rule_id: str, rule: dict) -> str:
    """Long badge title with spacing, e.g. Rule 01 : 언어 규칙 """
    fixed = BADGE_TITLE_BY_RULE_ID.get(rule_id)
    if fixed:
        return fixed
    rtype = rule.get("type", "unknown")
    type_ko = TYPE_LABELS.get(rtype, rtype)
    return f"{format_rule_id_heading(rule_id)} : {type_ko} 규칙 "


def detail_list_paren(rule_id: str, rule: dict) -> str:
    """Parenthetical in scoring detail lines, e.g. 언어 규칙 / 형식·길이."""
    fixed = DETAIL_PAREN_BY_RULE_ID.get(rule_id)
    if fixed:
        return fixed
    rtype = rule.get("type", "unknown")
    return TYPE_LABELS.get(rtype, str(rtype))


def rule_pill_category_prefix(rule_id: str, rule: dict) -> str:
    """Category span text before rule body, including trailing space before colon pair."""
    fixed = PILL_CATEGORY_PREFIX_BY_RULE_ID.get(rule_id)
    if fixed:
        return fixed
    rtype = rule.get("type", "unknown")
    type_ko = TYPE_LABELS.get(rtype, rtype)
    return f"{type_ko} 규칙: "


def render_rule_pills(rules: list[dict]) -> str:
    """Render active rules as compact pills."""
    pills = []
    for rule in rules:
        rid = rule.get("rule_id", "")
        prefix = rule_pill_category_prefix(rid, rule)
        match = re.match(r"^R(\d+)$", rid or "")
        if match:
            strong = f"<strong>Rule {int(match.group(1)):02d}</strong>"
        else:
            strong = f"<strong>{escape(rid)}</strong>"
        body = rule.get("text", "")
        pills.append(
            "<span class='rule-pill'>"
            f"{strong}"
            f"<span>{prefix}</span>"
            f"<em> {escape(body)}</em>"
            "</span>"
        )
    return "\n".join(pills)


def summarize_bucket_example(
    records: list[dict],
    *,
    attack: str,
    rule_count: int,
    turn_count: int,
    title: str,
    summary: str,
) -> dict:
    """Summarize how one `(attack, rule_count, turn_count)` bucket is assembled."""
    subset = [
        record
        for record in records
        if record.get("attack_intensity") == attack
        and record.get("rule_count") == rule_count
        and record.get("turn_count") == turn_count
    ]
    if not subset:
        raise ValueError(
            f"No records found for bucket attack={attack}, rule_count={rule_count}, turn_count={turn_count}"
        )

    grouped: dict[tuple[str, ...], dict] = {}
    scenario_rep_counts: dict[str, set[int]] = {}
    for record in subset:
        rule_ids = tuple(sorted(rule.get("rule_id", "") for rule in record.get("rules", [])))
        case_id = record.get("case_id", "")
        rep = int(record.get("rep", 0))
        group = grouped.setdefault(rule_ids, {"case_ids": set(), "run_count": 0, "rep_values": set()})
        group["case_ids"].add(case_id)
        group["run_count"] += 1
        group["rep_values"].add(rep)
        scenario_rep_counts.setdefault(case_id, set()).add(rep)

    group_views = []
    for index, (rule_ids, payload) in enumerate(sorted(grouped.items())):
        letter = chr(ord("A") + index)
        case_ids = sorted(payload["case_ids"])
        rep_counts = sorted({len(scenario_rep_counts[case_id]) for case_id in case_ids})
        group_views.append(
            {
                "letter": letter,
                "rule_ids": list(rule_ids),
                "case_ids": case_ids,
                "scenario_count": len(case_ids),
                "run_count": payload["run_count"],
                "rep_count": rep_counts[0] if len(rep_counts) == 1 else None,
            }
        )

    rep_counts = sorted({len(rep_values) for rep_values in scenario_rep_counts.values()})
    variant_counts = sorted({group["scenario_count"] for group in group_views})

    return {
        "attack": attack,
        "attack_label": attack_label(attack),
        "rule_count": rule_count,
        "turn_count": turn_count,
        "title": title,
        "summary": summary,
        "bucket_label": f"[{attack_label(attack)}, R={rule_count}, T={turn_count}]",
        "run_count": len(subset),
        "scenario_count": len(scenario_rep_counts),
        "rule_set_count": len(group_views),
        "variant_count": variant_counts[0] if len(variant_counts) == 1 else None,
        "rep_count": rep_counts[0] if len(rep_counts) == 1 else None,
        "groups": group_views,
        "all_case_ids": sorted(scenario_rep_counts),
    }


def build_bucket_examples(records: list[dict]) -> list[dict]:
    """Build explainer payloads for the bucket-aggregation section."""
    return [
        summarize_bucket_example(records, **spec)
        for spec in BUCKET_EXAMPLE_SPECS
    ]


def bucket_formula(example: dict) -> str:
    """Human-friendly formula for one aggregated chart point."""
    if example.get("variant_count") and example.get("rep_count"):
        return (
            f"{example['rule_set_count']}개 규칙 조합 × "
            f"조합당 {example['variant_count']}개 대화 변형 × "
            f"rep {example['rep_count']}회 = 총 {example['run_count']} runs"
        )
    if example.get("rep_count"):
        return (
            f"{example['scenario_count']}개 고유 시나리오 × "
            f"rep {example['rep_count']}회 = 총 {example['run_count']} runs"
        )
    return f"{example['scenario_count']}개 고유 시나리오를 합쳐 총 {example['run_count']} runs"


def render_bucket_group(group: dict, *, attack_label_text: str, turn_count: int) -> str:
    """Render one rule-set subgroup inside a bucket diagram."""
    rule_text = ", ".join(group["rule_ids"])
    chips = []
    for index, case_id in enumerate(group["case_ids"], start=1):
        chips.append(
            "<span class='bucket-chip'>"
            f"<strong>{group['letter']}{index}</strong>"
            f"<em>{escape(case_id)}</em>"
            "</span>"
        )

    if len(group["rule_ids"]) == 1:
        header_copy = f"{attack_label_text} + {group['rule_ids'][0]}만 사용 + {turn_count}턴"
    else:
        header_copy = f"{attack_label_text} + 규칙 {len(group['rule_ids'])}개 조합 + {turn_count}턴"

    if group.get("rep_count") is not None:
        foot_copy = (
            f"{group['scenario_count']}개 case_id × rep {group['rep_count']}회 = "
            f"{group['run_count']} runs"
        )
    else:
        foot_copy = f"{group['scenario_count']}개 case_id를 합쳐 {group['run_count']} runs"

    return """
<article class="bucket-group-card">
  <div class="bucket-group-head">
    <strong>{letter} 그룹</strong>
    <span>{header_copy}</span>
  </div>
  <p class="bucket-group-copy"><strong>System prompt 규칙:</strong> {rule_text}</p>
  <div class="bucket-chip-list">
    {chips}
  </div>
  <p class="bucket-group-foot">{foot_copy}</p>
</article>
""".format(
        letter=escape(group["letter"]),
        header_copy=escape(header_copy),
        rule_text=escape(rule_text),
        chips="\n".join(chips),
        foot_copy=escape(foot_copy),
    )


def render_bucket_example_card(example: dict) -> str:
    """Render one compact, text-first example card."""
    group_summaries = []
    for group in example["groups"]:
        group_summaries.append(
            "<li>"
            f"<strong>{escape(group['letter'])} 그룹</strong>: "
            f"{escape(', '.join(group['rule_ids']))} → "
            f"{escape(', '.join(group['case_ids']))}"
            "</li>"
        )

    rep_copy = (
        f"각 case_id마다 rep {example['rep_count']}회"
        if example.get("rep_count") is not None
        else "case_id별 rep 수는 데이터셋에서 확인"
    )

    return """
<article class="example-card">
  <p class="summary-eyebrow">Bucket example</p>
  <h3>{title}</h3>
  <p>{summary}</p>
  <ul class="example-list">
    <li><strong>규칙 조합 수</strong>: {rule_set_count}개</li>
    <li><strong>고유 case_id 수</strong>: {scenario_count}개 ({all_case_ids})</li>
    <li><strong>반복(rep)</strong>: {rep_copy}</li>
    <li><strong>총 결과 수 (n)</strong>: {run_count}</li>
  </ul>
  <ul class="example-list group-summary-list">
    {group_summaries}
  </ul>
  <div class="formula-callout">{formula}</div>
</article>
""".format(
        title=escape(example["title"]),
        summary=escape(example["summary"]),
        rule_set_count=example["rule_set_count"],
        scenario_count=example["scenario_count"],
        all_case_ids=escape(", ".join(example["all_case_ids"])),
        rep_copy=escape(rep_copy),
        run_count=example["run_count"],
        group_summaries="\n".join(group_summaries),
        formula=escape(bucket_formula(example)),
    )


def render_bucket_explainer(examples: list[dict]) -> str:
    """Render the chart-point aggregation explainer section."""
    if not examples:
        return ""

    primary = examples[0]
    secondary_cards = "\n".join(render_bucket_example_card(example) for example in examples)
    primary_groups = "\n".join(
        render_bucket_group(
            group,
            attack_label_text=primary["attack_label"],
            turn_count=primary["turn_count"],
        )
        for group in primary["groups"]
    )

    return """
<section class="explainer-section" aria-labelledby="bucket-explainer-title">
  <div class="case-heading">
    <div>
      <p class="eyebrow">How to read one point</p>
      <h2 id="bucket-explainer-title">Q1 그래프의 점 하나는 “한 run”이 아니라 “큰 바구니”입니다</h2>
      <p class="case-why">
        점의 이름표에는 <strong>공격 종류</strong>, <strong>규칙 개수</strong>, <strong>턴 수</strong>만 적혀 있습니다.
        어떤 규칙 조합을 썼는지와 어떤 대화 변형인지가 이름표에 없기 때문에,
        조건만 맞으면 서로 다른 시나리오 결과도 한 바구니에 함께 담겨 평균됩니다.
      </p>
    </div>
  </div>
  <div class="explainer-grid">
    <figure class="figure-card">
      <img src="figures/q1_compliance_by_rule_count.png" alt="Q1 compliance by rule count chart">
      <figcaption>
        해석 포인트: 차트의 한 점은 정확히 <code>(attack, rule_count, turn_count)</code> 집계 키를 가진
        결과 묶음 하나를 뜻합니다.
      </figcaption>
    </figure>
    <div class="bucket-card">
      <div class="bucket-key">
        <p class="summary-eyebrow">집계 키 / bucket label</p>
        <strong>{bucket_label}</strong>
        <div class="bucket-tags">
          <span>Attack = {attack_label}</span>
          <span>Rule count = {rule_count}</span>
          <span>Turn count = {turn_count}</span>
        </div>
        <p>
          이 이름표에는 <strong>R01인지 R03인지</strong>, <strong>어느 대화 패턴인지</strong>,
          <strong>rep가 몇 번째인지</strong>가 없습니다.
          그래서 A/B/C처럼 서로 다른 system prompt와 서로 다른 input을 써도,
          집계 키가 같으면 코드에서는 한 점으로 평균을 냅니다.
        </p>
      </div>
      <div class="formula-callout">{formula}</div>
      <div class="bucket-group-grid">
        {primary_groups}
      </div>
      <ul class="example-list emphasis-list">
        <li><strong>A1, A2, A3</strong>는 서로 같은 input이 아닙니다.</li>
        <li><strong>A 그룹</strong>과 <strong>B/C 그룹</strong>은 사용하는 system prompt 규칙 자체가 달라서 완전히 다른 시나리오입니다.</li>
        <li>그럼에도 모두 <strong>{bucket_label}</strong> 조건을 만족하므로 하나의 큰 바구니에 담깁니다.</li>
      </ul>
    </div>
  </div>
  <div class="example-grid">
    {secondary_cards}
  </div>
</section>
""".format(
        bucket_label=escape(primary["bucket_label"]),
        attack_label=escape(primary["attack_label"]),
        rule_count=primary["rule_count"],
        turn_count=primary["turn_count"],
        formula=escape(bucket_formula(primary)),
        primary_groups=primary_groups,
        secondary_cards=secondary_cards,
    )


def render_turn(turn_result: dict, rule_index: dict[str, dict]) -> str:
    """Render one turn in the transcript."""
    badges = []
    details = []
    for score in turn_result.get("scores", []):
        rid = score.get("rule_id", "")
        rule = rule_index.get(rid, {})
        status = badge_label(score.get("pass"))
        css_class = badge_class(score.get("pass"))
        title = score_badge_strong_title(rid, rule)
        paren = detail_list_paren(rid, rule)
        heading = format_rule_id_heading(rid)
        badges.append(
            "<span class='score-badge "
            f"{css_class}'>"
            f"<strong>{escape(title)}</strong>"
            f"<span class='badge-status'>{status}</span>"
            "</span>"
        )
        details.append(
            "<li>"
            f"<strong>{escape(heading)}</strong> "
            f"({escape(paren)}) - {status}: {escape(score.get('detail', ''))}"
            "</li>"
        )

    compliance = float(turn_result.get("compliance_rate", 0.0))
    response_length = turn_result.get("response_length", 0)
    return """
<article class="turn-card">
  <div class="turn-header">
    <span class="turn-index">Turn {turn}</span>
    <span class="turn-stat">준수율 {compliance}</span>
    <span class="turn-stat">답변 길이 {response_length}자</span>
  </div>
  <div class="bubble-row user-row">
    <div class="speaker user">고객</div>
    <div class="bubble user-bubble">{user_message}</div>
  </div>
  <div class="bubble-row assistant-row">
    <div class="speaker assistant">고객 상담 에이전트</div>
    <div class="bubble assistant-bubble">{response}</div>
  </div>
  <div class="compliance-track">
    <div class="compliance-fill" style="width:{fill_width}%"></div>
  </div>
  <div class="score-badges">
    {badges}
  </div>
  <details class="score-details">
    <summary>턴 {turn} 채점 상세</summary>
    <ul>
      {details}
    </ul>
  </details>
</article>
""".format(
        turn=turn_result.get("turn", "?"),
        compliance=format_percent(compliance),
        response_length=response_length,
        user_message=format_text(turn_result.get("user_message", "")),
        response=format_text(turn_result.get("response", "")),
        fill_width=f"{compliance * 100:.1f}",
        badges="\n".join(badges),
        details="\n".join(details),
    )


def render_case_section(case_view: dict) -> str:
    """Render one representative case section."""
    record = case_view["record"]
    rules = record.get("rules", [])
    rule_index = {rule.get("rule_id", ""): rule for rule in rules}
    transcript = "\n".join(
        render_turn(turn_result, rule_index) for turn_result in record.get("turn_results", [])
    )
    failure_turn = case_view.get("first_failure_turn")
    failure_copy = f"T{failure_turn}" if failure_turn is not None else "No failure"
    eval_counts = case_view["eval_counts"]

    return """
<section id="{slug}" class="case-section">
  <div class="case-heading">
    <div>
      <p class="eyebrow">{attack_label} | R{rule_count} | T{turn_count}</p>
      <h2>{title}</h2>
      <p class="case-why">{why}</p>
    </div>
    <a class="jump-link" href="#top">Back to top</a>
  </div>
  <div class="metric-grid">
    <div class="metric-card">
      <span>Exact-cell mean</span>
      <strong>{cell_mean}</strong>
      <em>{cell_n} runs in this cell</em>
    </div>
    <div class="metric-card">
      <span>Chosen run</span>
      <strong>{run_final}</strong>
      <em>{case_id} / rep {rep}</em>
    </div>
    <div class="metric-card">
      <span>First failed turn</span>
      <strong>{failure_turn}</strong>
      <em>Research question {research_question}</em>
    </div>
    <div class="metric-card">
      <span>Rule eval summary</span>
      <strong>{fail_count} fail</strong>
      <em>{pass_count} pass, {na_count} not applicable</em>
    </div>
  </div>
  <details class="system-prompt">
    <summary>시스템 프롬프트 및 활성 규칙</summary>
    <div class="prompt-box">{system_prompt}</div>
    <div class="rule-pills">
      {rule_pills}
    </div>
  </details>
  <div class="transcript">
    {transcript}
  </div>
</section>
""".format(
        slug=escape(case_view["slug"]),
        attack_label=attack_label(record.get("attack_intensity", "")),
        rule_count=record.get("rule_count"),
        turn_count=record.get("turn_count"),
        title=escape(case_view["title"]),
        why=escape(case_view["why"]),
        cell_mean=format_percent(case_view["cell_mean"]),
        cell_n=case_view["cell_n"],
        run_final=format_percent(case_view["final_compliance"]),
        case_id=escape(record.get("case_id", "")),
        rep=record.get("rep", 0),
        failure_turn=escape(failure_copy),
        research_question=escape(record.get("research_question", "")),
        fail_count=eval_counts["fail"],
        pass_count=eval_counts["pass"],
        na_count=eval_counts["na"],
        system_prompt=format_text(record.get("system_prompt", "")),
        rule_pills=render_rule_pills(rules),
        transcript=transcript,
    )


def render_html(
    case_views: list[dict],
    matched_paths: list[str],
    bucket_examples: list[dict],
) -> str:
    """Render the full HTML document."""
    summary_cards = []
    for case_view in case_views:
        record = case_view["record"]
        summary_cards.append(
            """
<a class="summary-card" href="#{slug}">
  <span class="summary-eyebrow">{attack} / R{rule_count} / T{turn_count}</span>
  <strong>{title}</strong>
  <em>cell mean {cell_mean}, chosen run {run_final}</em>
</a>
""".format(
                slug=escape(case_view["slug"]),
                attack=attack_label(record.get("attack_intensity", "")).lower(),
                rule_count=record.get("rule_count"),
                turn_count=record.get("turn_count"),
                title=escape(case_view["title"]),
                cell_mean=format_percent(case_view["cell_mean"]),
                run_final=format_percent(case_view["final_compliance"]),
            )
        )

    sections = "\n".join(render_case_section(case_view) for case_view in case_views)
    bucket_explainer = render_bucket_explainer(bucket_examples)
    sources = "<br>".join(escape(path) for path in matched_paths)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    return """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Representative Experiment Chats</title>
  <style>
    :root {{
      --bg: #f4efe7;
      --ink: #1f2430;
      --muted: #5d6678;
      --card: rgba(255, 250, 243, 0.92);
      --line: rgba(48, 58, 77, 0.14);
      --accent: #135d66;
      --accent-2: #b85c38;
      --pass: #1d7a5a;
      --fail: #a92f4a;
      --na: #8c7a57;
      --user: #efe2d0;
      --assistant: #fdfbf6;
      --shadow: 0 16px 36px rgba(31, 36, 48, 0.12);
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Noto Sans KR", "Apple SD Gothic Neo", "SUIT", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(184, 92, 56, 0.14), transparent 24rem),
        radial-gradient(circle at top right, rgba(19, 93, 102, 0.16), transparent 26rem),
        linear-gradient(180deg, #f7f1e8 0%, #f3ede3 48%, #efe7db 100%);
      line-height: 1.55;
    }}
    .page {{
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 32px 0 56px;
    }}
    .hero {{
      padding: 30px;
      border: 1px solid var(--line);
      border-radius: 28px;
      background: linear-gradient(135deg, rgba(255, 250, 243, 0.92), rgba(246, 241, 232, 0.86));
      box-shadow: var(--shadow);
    }}
    .eyebrow {{
      margin: 0 0 8px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--accent);
      font-weight: 700;
    }}
    h1, h2 {{
      margin: 0;
      line-height: 1.12;
    }}
    .hero p {{
      max-width: 72ch;
      color: var(--muted);
    }}
    .hero-meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-top: 18px;
      color: var(--muted);
      font-size: 14px;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      margin: 22px 0 30px;
    }}
    .summary-card {{
      display: flex;
      flex-direction: column;
      gap: 6px;
      text-decoration: none;
      color: inherit;
      padding: 18px;
      border-radius: 20px;
      border: 1px solid var(--line);
      background: var(--card);
      box-shadow: var(--shadow);
      transition: transform 140ms ease, border-color 140ms ease;
    }}
    .summary-card:hover {{
      transform: translateY(-2px);
      border-color: rgba(19, 93, 102, 0.35);
    }}
    .summary-eyebrow {{
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--accent-2);
      font-weight: 700;
    }}
    .summary-card strong {{
      font-size: 18px;
    }}
    .summary-card em {{
      font-style: normal;
      color: var(--muted);
      font-size: 14px;
    }}
    .explainer-section {{
      margin: 24px 0 26px;
      padding: 26px;
      border-radius: 28px;
      border: 1px solid var(--line);
      background: rgba(255, 251, 245, 0.92);
      box-shadow: var(--shadow);
    }}
    .explainer-grid {{
      display: grid;
      grid-template-columns: minmax(280px, 0.95fr) minmax(340px, 1.05fr);
      gap: 18px;
      align-items: start;
      margin-top: 18px;
    }}
    .figure-card,
    .bucket-card,
    .example-card {{
      margin: 0;
      padding: 18px;
      border-radius: 22px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
    }}
    .figure-card img {{
      display: block;
      width: 100%;
      height: auto;
      border-radius: 16px;
      border: 1px solid rgba(48, 58, 77, 0.12);
      background: #fff;
    }}
    .figure-card figcaption {{
      margin-top: 12px;
      color: var(--muted);
      font-size: 14px;
    }}
    .figure-card code {{
      padding: 2px 6px;
      border-radius: 999px;
      background: rgba(19, 93, 102, 0.08);
      color: var(--accent);
      font-family: "SFMono-Regular", "Menlo", monospace;
      font-size: 12px;
    }}
    .bucket-card {{
      display: grid;
      gap: 14px;
    }}
    .bucket-key strong {{
      display: block;
      font-size: 24px;
      margin-bottom: 10px;
    }}
    .bucket-key p {{
      margin: 0;
      color: var(--muted);
    }}
    .bucket-tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 10px 0 12px;
    }}
    .bucket-tags span {{
      padding: 8px 12px;
      border-radius: 999px;
      font-size: 13px;
      border: 1px solid rgba(19, 93, 102, 0.14);
      background: rgba(19, 93, 102, 0.08);
      color: var(--accent);
      font-weight: 700;
    }}
    .formula-callout {{
      padding: 14px 16px;
      border-radius: 18px;
      background: linear-gradient(135deg, rgba(19, 93, 102, 0.1), rgba(184, 92, 56, 0.09));
      border: 1px solid rgba(19, 93, 102, 0.12);
      font-weight: 700;
    }}
    .bucket-group-grid,
    .example-grid {{
      display: grid;
      gap: 12px;
    }}
    .bucket-group-grid {{
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }}
    .example-grid {{
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      margin-top: 18px;
    }}
    .bucket-group-card {{
      padding: 16px;
      border-radius: 18px;
      border: 1px solid rgba(48, 58, 77, 0.12);
      background: rgba(239, 226, 208, 0.34);
    }}
    .bucket-group-head {{
      display: flex;
      flex-direction: column;
      gap: 4px;
      margin-bottom: 10px;
    }}
    .bucket-group-head strong {{
      font-size: 15px;
      color: var(--accent);
    }}
    .bucket-group-head span,
    .bucket-group-copy,
    .bucket-group-foot {{
      color: var(--muted);
      font-size: 14px;
    }}
    .bucket-group-copy,
    .bucket-group-foot {{
      margin: 0;
    }}
    .bucket-chip-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 12px 0;
    }}
    .bucket-chip {{
      display: inline-flex;
      flex-direction: row;
      flex-wrap: nowrap;
      align-items: baseline;
      gap: 0.35em;
      min-width: 76px;
      max-width: max-content;
      padding: 10px 12px;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.82);
      border: 1px solid rgba(48, 58, 77, 0.1);
      white-space: nowrap;
    }}
    .bucket-chip strong {{
      font-size: 13px;
    }}
    .bucket-chip em {{
      font-style: normal;
      font-size: 12px;
      color: var(--muted);
      white-space: nowrap;
    }}
    .bucket-chip-row {{
      display: flex;
      gap: 8px;
      flex-wrap: nowrap;
      overflow-x: auto;
      padding-bottom: 6px;
      -webkit-overflow-scrolling: touch;
    }}
    .bucket-chip-row--center {{
      justify-content: center;
    }}
    .example-card h3 {{
      margin: 0 0 10px;
      line-height: 1.25;
    }}
    .example-card p {{
      margin: 0 0 12px;
      color: var(--muted);
    }}
    .example-list {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
    }}
    .example-list li + li {{
      margin-top: 6px;
    }}
    .group-summary-list {{
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px dashed rgba(48, 58, 77, 0.16);
    }}
    .emphasis-list strong {{
      color: var(--ink);
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 18px;
    }}
    .legend span {{
      padding: 8px 12px;
      border-radius: 999px;
      font-size: 13px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.44);
    }}
    .case-section {{
      margin-top: 26px;
      padding: 26px;
      border-radius: 28px;
      border: 1px solid var(--line);
      background: rgba(255, 251, 245, 0.9);
      box-shadow: var(--shadow);
    }}
    .case-heading {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }}
    .case-why {{
      margin: 10px 0 0;
      color: var(--muted);
      max-width: 70ch;
    }}
    .jump-link {{
      white-space: nowrap;
      text-decoration: none;
      color: var(--accent);
      font-weight: 700;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    .metric-card {{
      padding: 16px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.62);
      border: 1px solid var(--line);
    }}
    .metric-card span {{
      display: block;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .metric-card strong {{
      display: block;
      font-size: 24px;
      margin-bottom: 4px;
    }}
    .metric-card em {{
      font-style: normal;
      color: var(--muted);
      font-size: 14px;
    }}
    .system-prompt {{
      margin-bottom: 18px;
      border: 1px solid var(--line);
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.48);
      overflow: hidden;
    }}
    .system-prompt summary,
    .score-details summary {{
      cursor: pointer;
      font-weight: 700;
      padding: 14px 16px;
    }}
    .prompt-box {{
      padding: 0 16px 12px;
      color: var(--ink);
      border-top: 1px solid var(--line);
    }}
    .rule-pills {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      padding: 0 16px 16px;
    }}
    .rule-pill {{
      display: flex;
      flex-direction: column;
      gap: 4px;
      max-width: 280px;
      padding: 12px 14px;
      border-radius: 16px;
      background: rgba(239, 226, 208, 0.55);
      border: 1px solid rgba(48, 58, 77, 0.1);
    }}
    .rule-pill strong {{
      font-size: 15px;
    }}
    .rule-pill span {{
      font-size: 12px;
      font-weight: 700;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .rule-pill em {{
      font-style: normal;
      font-size: 14px;
      color: var(--muted);
    }}
    .transcript {{
      display: grid;
      gap: 18px;
    }}
    .turn-card {{
      padding: 18px;
      border-radius: 22px;
      background: rgba(255, 255, 255, 0.68);
      border: 1px solid rgba(48, 58, 77, 0.1);
    }}
    .turn-header {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-bottom: 14px;
    }}
    .turn-index {{
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(19, 93, 102, 0.12);
      color: var(--accent);
      font-weight: 700;
      font-size: 13px;
    }}
    .turn-stat {{
      color: var(--muted);
      font-size: 14px;
    }}
    .bubble-row {{
      display: grid;
      grid-template-columns: 72px 1fr;
      gap: 12px;
      margin-bottom: 12px;
      align-items: start;
    }}
    .speaker {{
      padding-top: 10px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .bubble {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid rgba(48, 58, 77, 0.1);
      white-space: normal;
      word-break: keep-all;
    }}
    .user-bubble {{
      background: var(--user);
      border-top-left-radius: 6px;
    }}
    .assistant-bubble {{
      background: var(--assistant);
      border-top-left-radius: 6px;
    }}
    .compliance-track {{
      width: 100%;
      height: 8px;
      margin: 4px 0 14px;
      border-radius: 999px;
      background: rgba(48, 58, 77, 0.09);
      overflow: hidden;
    }}
    .compliance-fill {{
      height: 100%;
      background: linear-gradient(90deg, #b85c38, #135d66);
      border-radius: 999px;
    }}
    .score-badges {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .score-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 10px;
      border-radius: 999px;
      font-size: 13px;
      border: 1px solid transparent;
    }}
    .score-badge strong {{
      font-size: 12px;
    }}
    .score-badge .badge-status {{
      font-style: normal;
      font-weight: 700;
      letter-spacing: 0.04em;
      color: inherit;
    }}
    .score-badge.pass {{
      background: rgba(29, 122, 90, 0.1);
      border-color: rgba(29, 122, 90, 0.2);
      color: var(--pass);
    }}
    .score-badge.fail {{
      background: rgba(169, 47, 74, 0.1);
      border-color: rgba(169, 47, 74, 0.2);
      color: var(--fail);
    }}
    .score-badge.na {{
      background: rgba(140, 122, 87, 0.12);
      border-color: rgba(140, 122, 87, 0.2);
      color: var(--na);
    }}
    .score-details {{
      margin-top: 12px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.48);
    }}
    .score-details ul {{
      margin: 0;
      padding: 0 16px 16px 34px;
      color: var(--muted);
    }}
    @media (max-width: 760px) {{
      .page {{
        width: min(100vw - 20px, 1180px);
        padding-top: 20px;
      }}
      .hero,
      .explainer-section,
      .case-section {{
        padding: 18px;
        border-radius: 22px;
      }}
      .explainer-grid {{
        grid-template-columns: 1fr;
      }}
      .bubble-row {{
        grid-template-columns: 1fr;
        gap: 6px;
      }}
      .speaker {{
        padding-top: 0;
      }}
      .case-heading {{
        flex-direction: column;
      }}
    }}
  </style>
</head>
<body>
  <main id="top" class="page">
    <header class="hero">
      <p class="eyebrow">Representative Case Walkthrough</p>
      <h1>final_report.md를 실제 멀티턴 채팅으로 풀어본 4개 사례</h1>
      <p>
        이 페이지는 보고서의 평균 그래프를 바로 이해하기 어렵다는 문제를 줄이기 위해 만들었습니다.
        각 사례는 정확한 실험 셀 안에서 final-turn compliance가 평균에 가장 가까운 run 하나를 골라,
        실제 사용자 메시지와 모델 응답, 그리고 턴별 rule scoring을 채팅방처럼 보여줍니다.
      </p>
      <div class="hero-meta">
        <div><strong>Generated</strong><br>{generated_at}</div>
        <div><strong>Source artifact</strong><br>{sources}</div>
        <div><strong>Selection rule</strong><br>Exact-cell mean에 가장 가까운 run</div>
      </div>
    </header>
    {bucket_explainer}
    <section class="summary-grid">
      {summary_cards}
    </section>
    <section class="legend" aria-label="legend">
      <span>PASS: 해당 턴에서 규칙 준수</span>
      <span>FAIL: 해당 턴에서 규칙 위반</span>
      <span>N/A: 그 턴에는 적용할 수 없는 규칙</span>
    </section>
    {sections}
  </main>
</body>
</html>
""".format(
        generated_at=escape(generated_at),
        sources=sources,
        bucket_explainer=bucket_explainer,
        summary_cards="\n".join(summary_cards),
        sections=sections,
    )


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        nargs="*",
        help="Input JSONL files or glob patterns. Defaults to fast_results_*.jsonl",
    )
    parser.add_argument(
        "--output",
        default=str(REPORT_DIR / "final_report_case_gallery.html"),
        help="Output HTML path",
    )
    args = parser.parse_args()

    input_patterns = resolve_input_patterns(args.input)
    if not input_patterns:
        raise SystemExit("No input result files found.")

    records, matched_paths = load_results(input_patterns)
    case_views = build_case_views(records)
    bucket_examples = build_bucket_examples(records)
    html = render_html(case_views, matched_paths, bucket_examples)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()

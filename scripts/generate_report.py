"""Generate presentation-ready report figures from experiment results.

Default behavior prefers the full `fast_results_*.jsonl` artifact because it
contains the per-record `rules` metadata needed for rule-type aggregation in Q2.

Usage:
    python3 scripts/generate_report.py
    python3 scripts/generate_report.py --input data/outputs/main_experiment/fast_results_*.jsonl
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MPL_CACHE_DIR = ROOT / ".tmp" / "matplotlib"
MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TURN_COUNTS = [1, 5, 10, 15]
RULE_COUNTS = [1, 3, 5, 7]
ATTACK_TYPES = ["benign", "adversarial"]
RULE_TYPES = ["language", "format", "behavioral", "persona"]
RULE_TYPE_LABELS = {
    "language": "언어",
    "format": "형식",
    "behavioral": "행동",
    "persona": "페르소나",
}

DEFAULT_FAST_PATTERN = str(
    ROOT / "data" / "outputs" / "main_experiment" / "fast_results_*.jsonl"
)
DEFAULT_RESULTS_PATTERN = str(
    ROOT / "data" / "outputs" / "main_experiment" / "results_*.jsonl"
)

# Korean font setup
for font_name in ["AppleGothic", "NanumGothic", "Malgun Gothic"]:
    if any(font_name in f.name for f in fm.fontManager.ttflist):
        plt.rcParams["font.family"] = font_name
        break
plt.rcParams["axes.unicode_minus"] = False

REPORT_DIR = ROOT / "docs" / "outputs"
FIG_DIR = REPORT_DIR / "figures"


def resolve_input_patterns(input_patterns: list[str] | None = None) -> list[str]:
    """어떤 JSONL 결과 파일(들)을 읽을지 정해 주는 함수다.

    `--input`을 안 주고 실행하면, `fast_results_*.jsonl`이 있으면 그걸 쓰고(규칙 `rules` 정보가 있어 Q2 그림에 필요),
    없으면 `results_*.jsonl`을 쓴다.

    인자:
        input_patterns: 파일 경로나 `*`가 들어간 패턴 문자열들. None이면 위 규칙으로 자동 선택.

    반환:
        나중에 `glob`으로 실제 파일을 찾을 때 쓸 문자열 리스트.
    """
    if input_patterns:
        return input_patterns

    fast_matches = sorted(glob.glob(DEFAULT_FAST_PATTERN))
    if fast_matches:
        return fast_matches

    return sorted(glob.glob(DEFAULT_RESULTS_PATTERN))


def load_results(input_patterns: list[str]) -> list[dict]:
    """JSONL 파일에서 실험 결과 한 줄씩 읽어서, 파이썬 dict들의 리스트로 만든다.

    JSONL은 "한 줄에 JSON 객체 하나"인 텍스트 파일 형식이다.
    각 줄을 `json.loads`로 dict로 바꾼 뒤, 마지막에 `dedupe_records`로 중복을 정리한다.

    인자:
        input_patterns: 읽을 파일 경로 또는 glob 패턴 문자열들의 리스트.

    반환:
        실험 1회분을 나타내는 dict들의 리스트(중복 제거 후).
    """
    records: list[dict] = []
    matched_paths: list[str] = []

    for pattern in input_patterns:
        matches = sorted(glob.glob(pattern))
        if not matches and Path(pattern).exists():
            matches = [pattern]

        matched_paths.extend(matches)
        for path in matches:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))

    logger.info("Matched %d input files", len(matched_paths))
    for path in matched_paths:
        logger.info("  - %s", path)

    return dedupe_records(records)


def dedupe_records(records: list[dict]) -> list[dict]:
    """같은 실험이 여러 파일에 겹쳐 있을 때, 하나만 남기고 정리한다.

    `results_*.jsonl`과 `fast_results_*.jsonl` 둘 다 있으면, 같은 (case_id, rep, model)을
    가리키는 줄이 중복될 수 있다. fast 쪽에는 규칙 종류(`rules`)가 더 자세히 있는 경우가 많다.
    키가 같으면 `record_priority`로 더 유용한 쪽 한 줄만 남긴다.

    인자:
        records: 여러 파일에서 모은 dict 리스트(아직 중복이 있을 수 있음).

    반환:
        중복이 제거되고 정렬된 dict 리스트.
    """

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
            r.get("model", ""),
            r.get("rule_count", 0),
            r.get("turn_count", 0),
            r.get("attack_intensity", ""),
            r.get("case_id", ""),
            r.get("rep", 0),
        )
    )
    return deduped


def record_priority(record: dict) -> tuple[int, int]:
    """`dedupe_records`가 두 줄 중 어느 쪽을 남길지 비교할 때 쓰는 "점수" 튜플을 만든다.

    첫 번째 숫자: `rules`가 있으면 1, 없으면 0.
    두 번째 숫자: `turn_results` 리스트의 길이(기록된 턴이 많을수록 큼).
    파이썬은 튜플을 앞에서부터 차례로 비교하므로, 값이 더 큰 쪽이 "더 좋은 기록"으로 남는다.

    인자:
        record: 실험 1회분 dict.

    반환:
        (int, int) 형태의 튜플.
    """
    return (
        1 if record.get("rules") else 0,
        len(record.get("turn_results", [])),
    )


def mean_std_n(values: list[float]) -> dict[str, float | int]:
    """숫자들의 평균(mean), 표준편차(std), 개수(n)를 한 번에 구한다.

    리스트가 비어 있으면 mean·std는 nan(숫자 아님), n은 0이다.

    인자:
        values: 실수들의 리스트.

    반환:
        {"mean", "std", "n"} 키를 가진 작은 dict.
    """
    if not values:
        return {"mean": float("nan"), "std": float("nan"), "n": 0}
    return {
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "n": len(values),
    }


def build_rule_type_map(record: dict) -> dict[str, str]:
    """한 실험 기록 안에서 "규칙 ID → 규칙 종류(언어·형식 등)"를 잇는 작은 사전을 만든다.

    `record["rules"]`를 돌면서 rule_id와 type을 짝지은 dict를 만든다.

    인자:
        record: `rules` 목록이 들어 있는 실험 dict.

    반환:
        예: {"R1": "language", ...} 형태의 dict.
    """
    return {
        rule.get("rule_id", ""): rule.get("type", "unknown")
        for rule in record.get("rules", [])
    }


def aggregate_final_cell_stats(records: list[dict]) -> dict[tuple[str, int, int], dict]:
    """Q1·Q3 그래프용: 실험 "조건" 하나마다 마지막 턴 준수율을 모은다.

    조건은 (공격 종류, 규칙 개수, 대화 턴 수) 조합 하나를 뜻한다.
    각 기록의 `turn_results` 마지막 항목 `compliance_rate`를 모아,
    그 조건에 속한 모든 반복 실험에 대해 평균·표준편차를 구한다.

    인자:
        records: `dedupe_records` 이후의 기록 리스트.

    반환:
        키가 (attack_intensity, rule_count, turn_count)이고, 값이 `mean_std_n` 결과 dict인 큰 dict.
    """

    cell_values: dict[tuple[str, int, int], list[float]] = defaultdict(list)

    for record in records:
        turn_results = record.get("turn_results", [])
        if not turn_results:
            continue
        key = (
            record["attack_intensity"],
            record["rule_count"],
            record["turn_count"],
        )
        cell_values[key].append(turn_results[-1]["compliance_rate"])

    return {key: mean_std_n(values) for key, values in sorted(cell_values.items())}


def aggregate_rule_type_condition_stats(
    records: list[dict],
) -> dict[tuple[str, int, str], dict]:
    """Q2 히트맵용: (공격 종류, 턴 수, 규칙 유형)마다 통과 비율을 모은다.

    각 턴·각 규칙에 대한 채점(`scores`)이 있다. `pass`가 True/False인 것만 세고,
    None(해당 없음)은 빼서 공정하게 만든다. 규칙 ID는 `build_rule_type_map`으로 종류에 붙인다.

    인자:
        records: `rules` 메타데이터가 있는 기록들(없는 기록은 건너뛰고 경고 로그).

    반환:
        키가 (attack_intensity, turn_count, rule_type)이고, 값에 "mean"(통과 비율), "n"(표본 수)이 있는 dict.
    """

    stats: dict[tuple[str, int, str], dict[str, int]] = defaultdict(
        lambda: {"passes": 0, "n": 0}
    )
    missing_rule_metadata = 0

    for record in records:
        rule_type_map = build_rule_type_map(record)
        if not rule_type_map:
            missing_rule_metadata += 1
            continue

        for turn_result in record.get("turn_results", []):
            for score in turn_result.get("scores", []):
                passed = score.get("pass")
                if passed is None:
                    continue

                rule_type = rule_type_map.get(score.get("rule_id", ""), "unknown")
                key = (
                    record["attack_intensity"],
                    record["turn_count"],
                    rule_type,
                )
                stats[key]["passes"] += int(bool(passed))
                stats[key]["n"] += 1

    if missing_rule_metadata:
        logger.warning(
            "Skipped %d records without `rules` metadata while aggregating Q2",
            missing_rule_metadata,
        )

    aggregated: dict[tuple[str, int, str], dict] = {}
    for key, values in sorted(stats.items()):
        n = values["n"]
        aggregated[key] = {
            "mean": (values["passes"] / n) if n else None,
            "n": n,
        }
    return aggregated


def chart_compliance_by_rule_count(records: list[dict]) -> None:
    """연구 질문 Q1용 그림: 규칙 개수별로, 마지막 턴 준수율을 선 그래프로 그린다.

    가로축은 대화 턴 수, 세로축은 준수율(%). 점마다 표본 수 n을 적고, 세로 막대는 표준편차다.
    benign / adversarial 두 패널로 나눈다. 파일만 저장하고 화면에는 안 띄운다(`plt.close`).
    """
    final_stats = aggregate_final_cell_stats(records)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharey=True)
    colors = {1: "#1f77b4", 3: "#2ca02c", 5: "#ff7f0e", 7: "#d62728"}
    n_offsets = {1: 10, 3: 2, 5: -6, 7: -14}

    for ax, attack in zip(axes, ATTACK_TYPES):
        for rc in RULE_COUNTS:
            turns: list[int] = []
            means: list[float] = []
            stds: list[float] = []
            ns: list[int] = []

            for turn_count in TURN_COUNTS:
                stats = final_stats.get((attack, rc, turn_count))
                if not stats:
                    continue
                turns.append(turn_count)
                means.append(stats["mean"] * 100)
                stds.append(stats["std"] * 100)
                ns.append(int(stats["n"]))

            if not turns:
                continue

            ax.errorbar(
                turns,
                means,
                yerr=stds,
                marker="o",
                linewidth=2,
                markersize=6,
                capsize=3,
                color=colors[rc],
                label=f"R={rc}",
            )

            for x, y, n in zip(turns, means, ns):
                ax.annotate(
                    f"n={n}",
                    xy=(x, y),
                    xytext=(0, n_offsets[rc]),
                    textcoords="offset points",
                    ha="center",
                    fontsize=7,
                    color=colors[rc],
                )

        ax.set_title(f"{attack} (exact-cell final-turn mean)", fontsize=13)
        ax.set_xlabel("Turn Count", fontsize=12)
        ax.set_ylabel("Final-turn Compliance (%)", fontsize=12)
        ax.set_xticks(TURN_COUNTS)
        ax.set_ylim(-5, 105)
        ax.axhline(y=80, color="orange", linestyle="--", alpha=0.4, linewidth=1)
        ax.axhline(y=50, color="red", linestyle="--", alpha=0.4, linewidth=1)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=10)

    fig.suptitle("Q1: Final-turn Compliance by Rule Count", fontsize=15, y=1.02)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "q1_compliance_by_rule_count.png", dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Saved q1_compliance_by_rule_count.png")


def chart_per_rule_type(records: list[dict]) -> None:
    """연구 질문 Q2용: 규칙 유형×턴 수 히트맵을 benign / adversarial 두 칸으로 그린다.

    색은 통과 비율이고, 칸마다 비율과 n을 적는다. 숫자는 `aggregate_rule_type_condition_stats`에서 만든다.
    """
    type_stats = aggregate_rule_type_condition_stats(records)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True, constrained_layout=True)
    cmap = plt.cm.YlOrRd.copy()
    cmap.set_bad(color="#e6e6e6")

    for ax, attack in zip(axes, ATTACK_TYPES):
        matrix = np.full((len(RULE_TYPES), len(TURN_COUNTS)), np.nan)
        count_matrix = np.zeros((len(RULE_TYPES), len(TURN_COUNTS)), dtype=int)

        for row_idx, rule_type in enumerate(RULE_TYPES):
            for col_idx, turn_count in enumerate(TURN_COUNTS):
                stats = type_stats.get((attack, turn_count, rule_type))
                if not stats:
                    continue

                matrix[row_idx, col_idx] = stats["mean"] * 100
                count_matrix[row_idx, col_idx] = int(stats["n"])

        image = ax.imshow(matrix, vmin=0, vmax=100, cmap=cmap, aspect="auto")
        ax.set_title(f"{attack} (all-turn applicable pass rate)", fontsize=12)
        ax.set_xticks(range(len(TURN_COUNTS)))
        ax.set_xticklabels([str(t) for t in TURN_COUNTS], fontsize=10)
        ax.set_yticks(range(len(RULE_TYPES)))
        ax.set_yticklabels([RULE_TYPE_LABELS[t] for t in RULE_TYPES], fontsize=10)
        ax.set_xlabel("Turn Count", fontsize=11)
        ax.set_ylabel("Rule Type", fontsize=11)

        for row_idx, rule_type in enumerate(RULE_TYPES):
            for col_idx, turn_count in enumerate(TURN_COUNTS):
                n = count_matrix[row_idx, col_idx]
                if n == 0:
                    label = "N/A\nn=0"
                else:
                    value = matrix[row_idx, col_idx]
                    label = f"{value:.0f}%\nn={n}"

                text_color = "black"
                if not np.isnan(matrix[row_idx, col_idx]) and matrix[row_idx, col_idx] >= 65:
                    text_color = "white"

                ax.text(
                    col_idx,
                    row_idx,
                    label,
                    ha="center",
                    va="center",
                    fontsize=9,
                    color=text_color,
                )

    cbar = fig.colorbar(image, ax=axes, fraction=0.03, pad=0.03)
    cbar.set_label("Pass Rate (%)", fontsize=11)
    fig.suptitle("Q2: Rule-type Pass Rate by Attack and Turn Count", fontsize=15, y=1.02)
    plt.savefig(FIG_DIR / "q2_per_rule_type.png", dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Saved q2_per_rule_type.png")


def chart_benign_vs_adversarial(records: list[dict]) -> None:
    """연구 질문 Q3용: Q1과 같은 "조건·마지막 턴" 평균이지만, 규칙 개수(R)마다 작은 그래프(2×2)로 나누고
    실선/점선과 색으로 benign vs adversarial을 비교한다.
    """
    final_stats = aggregate_final_cell_stats(records)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharex=True, sharey=True)
    attack_styles = {
        "benign": {"color": "#1f77b4", "linestyle": "-", "offset": 8},
        "adversarial": {"color": "#d62728", "linestyle": "--", "offset": -10},
    }

    for idx, rc in enumerate(RULE_COUNTS):
        ax = axes[idx // 2][idx % 2]

        for attack in ATTACK_TYPES:
            turns: list[int] = []
            means: list[float] = []
            stds: list[float] = []
            ns: list[int] = []

            for turn_count in TURN_COUNTS:
                stats = final_stats.get((attack, rc, turn_count))
                if not stats:
                    continue
                turns.append(turn_count)
                means.append(stats["mean"] * 100)
                stds.append(stats["std"] * 100)
                ns.append(int(stats["n"]))

            if not turns:
                continue

            style = attack_styles[attack]
            ax.errorbar(
                turns,
                means,
                yerr=stds,
                marker="o",
                linewidth=2,
                markersize=6,
                capsize=3,
                linestyle=style["linestyle"],
                color=style["color"],
                label=attack,
            )

            for x, y, n in zip(turns, means, ns):
                ax.annotate(
                    f"n={n}",
                    xy=(x, y),
                    xytext=(0, style["offset"]),
                    textcoords="offset points",
                    ha="center",
                    fontsize=7,
                    color=style["color"],
                )

        ax.set_title(f"R={rc}", fontsize=12)
        ax.set_xticks(TURN_COUNTS)
        ax.set_ylim(-5, 105)
        ax.axhline(y=80, color="orange", linestyle=":", alpha=0.4)
        ax.axhline(y=50, color="red", linestyle=":", alpha=0.4)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=9)
        ax.set_xlabel("Turn Count", fontsize=11)
        ax.set_ylabel("Final-turn Compliance (%)", fontsize=11)

    fig.suptitle("Q3: Benign vs Adversarial (exact-cell final-turn mean)", fontsize=15, y=1.01)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "q3_benign_vs_adversarial.png", dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Saved q3_benign_vs_adversarial.png")


def chart_heatmap(records: list[dict]) -> None:
    """대표적인 adversarial 실행 하나를 골라, 턴×규칙 칸마다 통과/실패/해당없음을 색으로 보여 준다.

    후보가 없으면 경고만 찍고 끝낸다. 그림 크기는 규칙 수·턴 수에 맞춘다.
    """
    candidates = [
        record
        for record in records
        if record["rule_count"] >= 5
        and record["attack_intensity"] == "adversarial"
        and record["turn_count"] >= 10
    ]
    if not candidates:
        candidates = [record for record in records if record["turn_count"] >= 5]
    if not candidates:
        logger.warning("No candidates available for heatmap")
        return

    best = max(candidates, key=lambda record: record["rule_count"] * record["turn_count"])
    rule_ids = [score["rule_id"] for score in best["turn_results"][0]["scores"]]
    turn_nums = [turn_result["turn"] for turn_result in best["turn_results"]]

    matrix = []
    for turn_result in best["turn_results"]:
        row = []
        for score in turn_result["scores"]:
            if score["pass"] is True:
                row.append(1.0)
            elif score["pass"] is False:
                row.append(0.0)
            else:
                row.append(0.5)
        matrix.append(row)

    from matplotlib.colors import BoundaryNorm, ListedColormap
    from matplotlib.patches import Patch

    fig, ax = plt.subplots(figsize=(max(8, len(rule_ids)), max(6, len(turn_nums) * 0.5)))
    cmap = ListedColormap(["#e74c3c", "#f0e68c", "#2ecc71"])
    norm = BoundaryNorm([0, 0.25, 0.75, 1.0], cmap.N)

    ax.imshow(np.array(matrix), cmap=cmap, norm=norm, aspect="auto")
    ax.set_xticks(range(len(rule_ids)))
    ax.set_xticklabels(rule_ids, fontsize=9, rotation=45)
    ax.set_yticks(range(len(turn_nums)))
    ax.set_yticklabels([f"T{turn}" for turn in turn_nums], fontsize=9)
    ax.set_xlabel("Rule", fontsize=11)
    ax.set_ylabel("Turn", fontsize=11)
    ax.set_title(
        f"{best['case_id']}: R{best['rule_count']} T{best['turn_count']} "
        f"{best['attack_intensity']} (rep={best.get('rep', 0)})",
        fontsize=12,
    )

    legend_elements = [
        Patch(facecolor="#2ecc71", label="Pass"),
        Patch(facecolor="#f0e68c", label="N/A"),
        Patch(facecolor="#e74c3c", label="Fail"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=9)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "heatmap_representative.png", dpi=150)
    plt.close()
    logger.info("Saved heatmap_representative.png")


def compute_summary(records: list[dict]) -> dict:
    """마크다운 리포트와 JSON 요약에 쓸 숫자들을 한곳에 모은다.

    조건별 마지막 턴 평균과, 준수율이 0.8·0.5 아래로 떨어진 첫 턴 번호 등을 계산한다.
    """
    summary: dict = {
        "total_runs": len(records),
        "models": sorted({record["model"] for record in records}),
        "timestamp": time.strftime("%Y-%m-%d %H:%M"),
    }

    condition_stats: dict[str, list[float]] = defaultdict(list)
    for record in records:
        turn_results = record.get("turn_results", [])
        if not turn_results:
            continue
        key = (
            f"R{record['rule_count']}_T{record['turn_count']}_{record['attack_intensity']}"
        )
        condition_stats[key].append(turn_results[-1]["compliance_rate"])

    summary["condition_means"] = {
        key: mean_std_n(values)
        for key, values in sorted(condition_stats.items())
    }

    do_ct: dict[str, dict[str, list[int]]] = {}
    for record in records:
        key = f"R{record['rule_count']}_{record['attack_intensity']}"
        if key not in do_ct:
            do_ct[key] = {"do_turns": [], "ct_turns": []}

        for turn_result in record.get("turn_results", []):
            if turn_result["compliance_rate"] < 0.8:
                do_ct[key]["do_turns"].append(turn_result["turn"])
                break

        for turn_result in record.get("turn_results", []):
            if turn_result["compliance_rate"] < 0.5:
                do_ct[key]["ct_turns"].append(turn_result["turn"])
                break

    summary["threshold_detection"] = {
        key: {
            "DO_mean_turn": (
                float(np.mean(values["do_turns"])) if values["do_turns"] else None
            ),
            "DO_n": len(values["do_turns"]),
            "CT_mean_turn": (
                float(np.mean(values["ct_turns"])) if values["ct_turns"] else None
            ),
            "CT_n": len(values["ct_turns"]),
        }
        for key, values in sorted(do_ct.items())
    }

    return summary


def generate_markdown(records: list[dict], summary: dict) -> str:
    """지금 만든 그림 경로와 표를 담은 마크다운 문자열 한 덩어리를 만든다.

    파일로 쓰기 전 단계이며, 반환값만 문자열이다.
    """
    lines = [
        "# Compliance Decay Experiment — Presentation Report",
        "",
        f"> **Generated**: {summary['timestamp']}",
        f"> **Runs analyzed**: {summary['total_runs']}",
        f"> **Models**: {', '.join(summary['models'])}",
        "",
        "---",
        "",
        "## 1. Figure Semantics",
        "",
        "- **Q1**: each point is the exact-cell final-turn mean for one `(rule_count, turn_count, attack_intensity)` condition. Error bars are ±1 SD. Each point is annotated with `n`.",
        "- **Q2**: each heatmap cell is the all-turn pass rate for one `(attack_intensity, turn_count, rule_type)` condition, counting only applicable rule evaluations (`pass is not None`).",
        "- **Q3**: each point is the same exact-cell final-turn mean as Q1, regrouped to compare benign vs adversarial within each `rule_count`.",
        "",
        "---",
        "",
        "## 2. Visualizations",
        "",
        "### 2.1 Q1: Final-turn Compliance by Rule Count",
        "![Q1](figures/q1_compliance_by_rule_count.png)",
        "",
        "### 2.2 Q2: Rule-type Pass Rate by Attack and Turn Count",
        "![Q2](figures/q2_per_rule_type.png)",
        "",
        "### 2.3 Q3: Benign vs Adversarial (exact-cell final-turn mean)",
        "![Q3](figures/q3_benign_vs_adversarial.png)",
        "",
        "### 2.4 Representative Heatmap",
        "![Heatmap](figures/heatmap_representative.png)",
        "",
        "---",
        "",
        "## 3. Final-turn Compliance by Condition",
        "",
        "| Condition | Mean Compliance | Std | N |",
        "|-----------|----------------|-----|---|",
    ]

    for key, stats in summary["condition_means"].items():
        lines.append(
            f"| {key} | {stats['mean']*100:.1f}% | ±{stats['std']*100:.1f}% | {stats['n']} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 4. Next Steps",
        "",
        "- [ ] Add a slide that explicitly defines one run, one cell, and one figure point.",
        "- [ ] Add a `rule_set_variant` appendix table for the curated combinations used at each `rule_count`.",
        "- [ ] Consider a deferred follow-up experiment with long-document/PDF input plus strict 200-char / 300-char output limits. This idea was noted but is out of scope for the current run.",
    ])

    if records:
        benign_finals = [
            record["turn_results"][-1]["compliance_rate"]
            for record in records
            if record["attack_intensity"] == "benign" and record.get("turn_results")
        ]
        adversarial_finals = [
            record["turn_results"][-1]["compliance_rate"]
            for record in records
            if record["attack_intensity"] == "adversarial" and record.get("turn_results")
        ]
        if benign_finals and adversarial_finals:
            gap = (np.mean(benign_finals) - np.mean(adversarial_finals)) * 100
            lines.extend([
                "",
                f"- Current overall benign vs adversarial final-turn gap: {gap:.1f}pp",
            ])

    return "\n".join(lines)


def main() -> None:
    """이 스크립트를 직접 실행할 때 시작되는 입구(entry point) 함수다.

    인자를 읽고, 데이터를 불러와 그림·JSON·마크다운을 저장한 뒤, 터미널에 요약을 조금 출력한다.
    """
    parser = argparse.ArgumentParser(description="Generate presentation-ready experiment figures.")
    parser.add_argument(
        "--input",
        nargs="+",
        default=None,
        help="Explicit files or glob patterns for result JSONL files.",
    )
    args = parser.parse_args()

    input_patterns = resolve_input_patterns(args.input)
    records = load_results(input_patterns)
    if not records:
        logger.error("No results found. Run the experiment first.")
        return

    logger.info("Loaded %d deduplicated result records", len(records))

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    chart_compliance_by_rule_count(records)
    chart_per_rule_type(records)
    chart_benign_vs_adversarial(records)
    chart_heatmap(records)

    summary = compute_summary(records)

    with open(REPORT_DIR / "experiment_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    logger.info("Saved experiment_summary.json")

    report = generate_markdown(records, summary)
    report_path = REPORT_DIR / "experiment_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("Saved %s", report_path)

    print(f"\n{'=' * 60}")
    print(f"Presentation report: {summary['total_runs']} deduplicated runs analyzed")
    print(f"{'=' * 60}")
    for key, stats in list(summary["condition_means"].items())[:10]:
        print(
            f"  {key}: {stats['mean']*100:.1f}% ± {stats['std']*100:.1f}% "
            f"(n={stats['n']})"
        )
    if len(summary["condition_means"]) > 10:
        print(f"  ... and {len(summary['condition_means']) - 10} more conditions")


if __name__ == "__main__":
    main()

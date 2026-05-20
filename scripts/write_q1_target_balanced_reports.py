"""Write Q1 target-balanced analysis report and presentation script from visualization outputs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VIS_DIR = (
    ROOT
    / "data"
    / "outputs"
    / "2026-05-18_q1_sampled_local_llama_gemma"
    / "ai_adjusted"
    / "q1_visualization"
)
DEFAULT_MANIFEST = ROOT / "data" / "outputs" / "2026-05-18_q1_sampled_local_llama_gemma" / "run_manifest.json"


def pct(value: Any) -> str:
    if value in (None, ""):
        return "N/A"
    value = float(value)
    if math.isnan(value):
        return "N/A"
    return f"{value * 100:.1f}%"


def pp(value: Any) -> str:
    if value in (None, ""):
        return "N/A"
    value = float(value)
    if math.isnan(value):
        return "N/A"
    return f"{value * 100:.1f}pp"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def row_value(rows: list[dict[str, str]], *, rule_count: int, turn_count: int, attack: str, metric: str) -> str:
    for row in rows:
        if int(row["rule_count"]) == rule_count and int(row["turn_count"]) == turn_count and row["attack_intensity"] == attack:
            return row.get(metric, "")
    return ""


def condition_markdown(rows: list[dict[str, str]]) -> str:
    lines = [
        "| rule_count | turn_count | attack | N | perfect_success | targeted_rule_success | non_target_failure | per_rule_pass_rate |",
        "|---:|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['rule_count']} | {row['turn_count']} | {row['attack_intensity']} | "
            f"{row.get('perfect_success_n','')} | {pct(row.get('perfect_success_mean'))} | "
            f"{pct(row.get('targeted_rule_success_mean'))} | {pct(row.get('non_target_failure_mean'))} | "
            f"{pct(row.get('per_rule_pass_rate_mean'))} |"
        )
    return "\n".join(lines)


def target_rule_markdown(rows: list[dict[str, str]]) -> str:
    # Compact appendix-style T=15 adversarial rows by target rule and rule_count.
    subset = [row for row in rows if row["attack_intensity"] == "adversarial" and int(row["turn_count"]) == 15]
    lines = [
        "| target_rule | rule_count | N | perfect_success | targeted_rule_success | non_target_failure |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in subset:
        lines.append(
            "| "
            f"{row['target_rule_id']} | {row['rule_count']} | {row.get('perfect_success_n','')} | "
            f"{pct(row.get('perfect_success_mean'))} | {pct(row.get('targeted_rule_success_mean'))} | "
            f"{pct(row.get('non_target_failure_mean'))} |"
        )
    return "\n".join(lines)


def write_report(vis_dir: Path, manifest: dict[str, Any], summary: dict[str, Any]) -> None:
    condition_rows = read_csv(vis_dir / "tables" / "q1_condition_final_turn_metrics.csv")
    target_rule_rows = read_csv(vis_dir / "tables" / "q1_target_rule_final_turn_metrics.csv")
    target_scope = summary.get("target_rule_scope", {})

    benign_r7_t15 = row_value(condition_rows, rule_count=7, turn_count=15, attack="benign", metric="perfect_success_mean")
    adv_r7_t15 = row_value(condition_rows, rule_count=7, turn_count=15, attack="adversarial", metric="perfect_success_mean")
    target_r7_t15 = row_value(condition_rows, rule_count=7, turn_count=15, attack="adversarial", metric="targeted_rule_success_mean")
    nontarget_r7_t15 = row_value(condition_rows, rule_count=7, turn_count=15, attack="adversarial", metric="non_target_failure_mean")

    report = f"""# Q1 Target-Balanced Analysis Report

## 1. Research Question

Q1은 **시스템 프롬프트에 동시에 포함되는 규칙 수(`rule_count`)와 대화 턴 수(`turn_count`)가 증가할 때, 복수 규칙의 final-turn 동시 준수율(`perfect_success`)이 어떻게 변하는가**를 확인한다. 이번 갱신본에서는 공격 대상 규칙을 R03 하나로 고정하지 않고, Q2 final injection profile에서 사용 가능한 target rule 전체를 균형 배치했다.

## 2. Experimental Design

- Target model: `{manifest.get('target_model')}`
- Judge model: `{manifest.get('judge_model')}`
- Temperature: `{manifest.get('temperature')}`
- Records: `{manifest.get('case_count')}` cases / `{manifest.get('target_turn_call_count')}` target turns
- Target-rule scope: {target_scope.get('label')}
- Target-rule distribution: `{summary.get('target_rule_ids')}`
- Excluded rule: R08, because the Q2 final injection set has no R08 target-specific prompt.
- Primary metric: `perfect_success`, i.e., all applicable/scorable active rules pass on the final turn.
- Secondary metrics: `targeted_rule_success`, `non_target_failure`, and legacy `per_rule_pass_rate`.
- Attack placement: T=5/10/15 conditions use the final two turns, with both `implicit→adversarial` and `adversarial→implicit` orders included and averaged. T=1 uses the single-adversarial baseline.

## 3. Key Results

- Mean benign strict `perfect_success` across condition cells: **{pct(summary.get('mean_benign_perfect_success'))}**
- Mean adversarial strict `perfect_success` across condition cells: **{pct(summary.get('mean_adversarial_perfect_success'))}**
- Mean adversarial targeted-rule success: **{pct(summary.get('mean_adversarial_targeted_rule_success'))}**
- Mean adversarial non-target failure: **{pct(summary.get('mean_adversarial_non_target_failure'))}**
- Mean benign−adversarial strict gap: **{pp(summary.get('mean_benign_minus_adversarial_gap'))}**

Most thesis-relevant stress cell (`rule_count=7`, `turn_count=15`):

- Benign `perfect_success`: **{pct(benign_r7_t15)}**
- Adversarial `perfect_success`: **{pct(adv_r7_t15)}**
- Adversarial `targeted_rule_success`: **{pct(target_r7_t15)}**
- Adversarial `non_target_failure`: **{pct(nontarget_r7_t15)}**

## 4. Condition-Level Table

{condition_markdown(condition_rows)}

## 5. Target-Rule Audit Table — T=15 adversarial

{target_rule_markdown(target_rule_rows)}

## 6. Interpretation

The target-balanced rerun is stronger than the earlier R03-only controlled run because target-rule difficulty is no longer hidden inside one prefix-format rule. The main condition table can be interpreted as an equal-weight target-rule average because each available target rule contributes the same number of records. Therefore, Q1 now supports the broader claim that strict simultaneous compliance degrades under longer context and larger active rule sets, not merely that R03 is vulnerable.

At the same time, the result should still be scoped carefully: the experiment uses the Q2-derived injection set, excludes R08 due to missing source prompts, and samples filler rule combinations rather than enumerating every possible combination.

## 7. Artifacts

- Summary JSON: `{vis_dir / 'q1_visualization_summary.json'}`
- Condition table: `{vis_dir / 'tables' / 'q1_condition_final_turn_metrics.csv'}`
- Target-rule table: `{vis_dir / 'tables' / 'q1_target_rule_final_turn_metrics.csv'}`
- Figures directory: `{vis_dir / 'figures'}`
- AI-adjusted JSONL: `{manifest.get('ai_adjusted_jsonl', 'see ai_adjusted directory')}`
"""
    (vis_dir / "q1_analysis_report.md").write_text(report, encoding="utf-8")

    script = f"""# Q1 Presentation Script — Target-Balanced Run

안녕하세요. 이번 슬라이드에서는 Research Question 1 결과를 설명드리겠습니다.

Q1의 질문은, 시스템 프롬프트 안에 동시에 들어가는 규칙 수가 많아지고 대화 턴이 길어질수록, 모델이 여러 규칙을 동시에 끝까지 지킬 수 있는가입니다. 여기서 핵심 지표는 `perfect_success`입니다. 이 값은 final turn에서 적용 가능한 모든 규칙을 동시에 만족해야만 1이 됩니다.

중요한 점은, 이번 최종 Q1은 이전 R03-only 실험이 아니라 target-balanced 실험이라는 점입니다. Q2 injection set에서 사용 가능한 R01, R02, R03, R04, R05, R06, R07, R09, R10을 모두 공격 대상으로 균형 배치했습니다. R08은 Q2 final set에 대응 prompt가 없어서 제외했습니다.

실험 규모는 총 {manifest.get('case_count')}개 case, {manifest.get('target_turn_call_count')}개 target-model turn입니다. temperature는 0.0으로 고정했고, 공격 rule 수는 한 개로 고정했습니다. T=5, 10, 15에서는 마지막 두 turn에 implicit attack과 adversarial attack을 배치했으며, 두 순서를 모두 실행해서 평균냈습니다.

결과를 보면, benign 조건의 평균 strict perfect_success는 {pct(summary.get('mean_benign_perfect_success'))}였고, adversarial 조건에서는 {pct(summary.get('mean_adversarial_perfect_success'))}로 낮아졌습니다. 특히 rule_count=7, turn_count=15의 stress condition에서는 adversarial perfect_success가 {pct(adv_r7_t15)}입니다.

이 결과가 의미하는 바는 단순히 특정 규칙 하나가 깨졌다는 것이 아닙니다. target rule을 전체적으로 균형 배치했는데도, 규칙 수와 대화 길이가 커질수록 final turn에서 모든 규칙을 동시에 만족하는 능력이 크게 약해졌다는 것입니다.

또 하나 중요한 관찰은 non-target failure입니다. 공격은 한 개 rule만 겨냥했지만, adversarial 조건에서 non-target failure 평균이 {pct(summary.get('mean_adversarial_non_target_failure'))}로 나타났습니다. 즉 injection은 target rule만 무너뜨리는 것이 아니라, 함께 들어간 다른 규칙들의 동시 준수도 흔들 수 있습니다.

따라서 Q1의 결론은 다음과 같습니다. 복수 규칙을 동시에 유지해야 하는 상황에서, rule_count와 turn_count가 증가하면 strict simultaneous compliance는 감소한다. 그리고 이 효과는 R03 prefix rule 하나에 한정된 것이 아니라, Q2에서 확보된 여러 target rule을 균형 배치한 평균에서도 관찰된다.
"""
    (vis_dir / "q1_presentation_script.md").write_text(script, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write Q1 target-balanced report/script.")
    parser.add_argument("--vis-dir", type=Path, default=DEFAULT_VIS_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    vis_dir = args.vis_dir if args.vis_dir.is_absolute() else ROOT / args.vis_dir
    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    summary = json.loads((vis_dir / "q1_visualization_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    write_report(vis_dir, manifest, summary)
    print(f"wrote {vis_dir / 'q1_analysis_report.md'}")
    print(f"wrote {vis_dir / 'q1_presentation_script.md'}")


if __name__ == "__main__":
    main()

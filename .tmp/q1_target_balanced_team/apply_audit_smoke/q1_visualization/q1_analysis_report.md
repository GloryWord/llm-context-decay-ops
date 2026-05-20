# Q1 Target-Balanced Analysis Report

## 1. Research Question

Q1은 **시스템 프롬프트에 동시에 포함되는 규칙 수(`rule_count`)와 대화 턴 수(`turn_count`)가 증가할 때, 복수 규칙의 final-turn 동시 준수율(`perfect_success`)이 어떻게 변하는가**를 확인한다. 이번 갱신본에서는 공격 대상 규칙을 R03 하나로 고정하지 않고, Q2 final injection profile에서 사용 가능한 target rule 전체를 균형 배치했다.

## 2. Experimental Design

- Target model: `hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4`
- Judge model: `cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit`
- Temperature: `0.0`
- Records: `341` cases / `2852` target turns
- Target-rule scope: R03 only
- Target-rule distribution: `{'R03': 341}`
- Excluded rule: R08, because the Q2 final injection set has no R08 target-specific prompt.
- Primary metric: `perfect_success`, i.e., all applicable/scorable active rules pass on the final turn.
- Secondary metrics: `targeted_rule_success`, `non_target_failure`, and legacy `per_rule_pass_rate`.
- Attack placement: T=5/10/15 conditions use the final two turns, with both `implicit→adversarial` and `adversarial→implicit` orders included and averaged. T=1 uses the single-adversarial baseline.

## 3. Key Results

- Mean benign strict `perfect_success` across condition cells: **48.8%**
- Mean adversarial strict `perfect_success` across condition cells: **0.0%**
- Mean adversarial targeted-rule success: **0.0%**
- Mean adversarial non-target failure: **77.4%**
- Mean benign−adversarial strict gap: **48.8pp**

Most thesis-relevant stress cell (`rule_count=7`, `turn_count=15`):

- Benign `perfect_success`: **20.0%**
- Adversarial `perfect_success`: **0.0%**
- Adversarial `targeted_rule_success`: **0.0%**
- Adversarial `non_target_failure`: **100.0%**

## 4. Condition-Level Table

| rule_count | turn_count | attack | N | perfect_success | targeted_rule_success | non_target_failure | per_rule_pass_rate |
|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | 1 | benign | 1 | 100.0% | N/A | N/A | 100.0% |
| 1 | 1 | adversarial | 1 | 0.0% | 0.0% | N/A | 0.0% |
| 1 | 5 | benign | 1 | 100.0% | N/A | N/A | 100.0% |
| 1 | 5 | adversarial | 2 | 0.0% | 0.0% | N/A | 0.0% |
| 1 | 10 | benign | 1 | 100.0% | N/A | N/A | 100.0% |
| 1 | 10 | adversarial | 2 | 0.0% | 0.0% | N/A | 0.0% |
| 1 | 15 | benign | 1 | 100.0% | N/A | N/A | 100.0% |
| 1 | 15 | adversarial | 2 | 0.0% | 0.0% | N/A | 0.0% |
| 3 | 1 | benign | 10 | 40.0% | N/A | N/A | 73.3% |
| 3 | 1 | adversarial | 10 | 0.0% | 0.0% | 50.0% | 36.7% |
| 3 | 5 | benign | 10 | 50.0% | N/A | N/A | 80.0% |
| 3 | 5 | adversarial | 20 | 0.0% | 0.0% | 58.8% | 27.5% |
| 3 | 10 | benign | 10 | 40.0% | N/A | N/A | 73.3% |
| 3 | 10 | adversarial | 20 | 0.0% | 0.0% | 40.0% | 42.5% |
| 3 | 15 | benign | 10 | 30.0% | N/A | N/A | 71.7% |
| 3 | 15 | adversarial | 20 | 0.0% | 0.0% | 64.7% | 26.7% |
| 5 | 1 | benign | 10 | 50.0% | N/A | N/A | 79.7% |
| 5 | 1 | adversarial | 10 | 0.0% | 0.0% | 80.0% | 41.8% |
| 5 | 5 | benign | 10 | 50.0% | N/A | N/A | 82.5% |
| 5 | 5 | adversarial | 20 | 0.0% | 0.0% | 80.0% | 43.3% |
| 5 | 10 | benign | 10 | 30.0% | N/A | N/A | 67.5% |
| 5 | 10 | adversarial | 20 | 0.0% | 0.0% | 80.0% | 35.9% |
| 5 | 15 | benign | 10 | 20.0% | N/A | N/A | 63.8% |
| 5 | 15 | adversarial | 20 | 0.0% | 0.0% | 80.0% | 37.1% |
| 7 | 1 | benign | 10 | 10.0% | N/A | N/A | 68.0% |
| 7 | 1 | adversarial | 10 | 0.0% | 0.0% | 100.0% | 47.5% |
| 7 | 5 | benign | 10 | 20.0% | N/A | N/A | 75.8% |
| 7 | 5 | adversarial | 20 | 0.0% | 0.0% | 100.0% | 45.8% |
| 7 | 10 | benign | 10 | 20.0% | N/A | N/A | 72.7% |
| 7 | 10 | adversarial | 20 | 0.0% | 0.0% | 95.0% | 41.9% |
| 7 | 15 | benign | 10 | 20.0% | N/A | N/A | 77.8% |
| 7 | 15 | adversarial | 20 | 0.0% | 0.0% | 100.0% | 39.2% |

## 5. Target-Rule Audit Table — T=15 adversarial

| target_rule | rule_count | N | perfect_success | targeted_rule_success | non_target_failure |
|---|---:|---:|---:|---:|---:|
| R03 | 1 | 2 | 0.0% | 0.0% | N/A |
| R03 | 3 | 20 | 0.0% | 0.0% | 64.7% |
| R03 | 5 | 20 | 0.0% | 0.0% | 80.0% |
| R03 | 7 | 20 | 0.0% | 0.0% | 100.0% |

## 6. Interpretation

The target-balanced rerun is stronger than the earlier R03-only controlled run because target-rule difficulty is no longer hidden inside one prefix-format rule. The main condition table can be interpreted as an equal-weight target-rule average because each available target rule contributes the same number of records. Therefore, Q1 now supports the broader claim that strict simultaneous compliance degrades under longer context and larger active rule sets, not merely that R03 is vulnerable.

At the same time, the result should still be scoped carefully: the experiment uses the Q2-derived injection set, excludes R08 due to missing source prompts, and samples filler rule combinations rather than enumerating every possible combination.

## 7. Artifacts

- Summary JSON: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/.tmp/q1_target_balanced_team/apply_audit_smoke/q1_visualization/q1_visualization_summary.json`
- Condition table: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/.tmp/q1_target_balanced_team/apply_audit_smoke/q1_visualization/tables/q1_condition_final_turn_metrics.csv`
- Target-rule table: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/.tmp/q1_target_balanced_team/apply_audit_smoke/q1_visualization/tables/q1_target_rule_final_turn_metrics.csv`
- Figures directory: `/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops/.tmp/q1_target_balanced_team/apply_audit_smoke/q1_visualization/figures`
- AI-adjusted JSONL: `see ai_adjusted directory`

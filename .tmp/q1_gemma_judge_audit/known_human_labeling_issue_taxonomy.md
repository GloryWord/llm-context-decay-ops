# Known human-labeling issue taxonomy for Gemma judge audit

Sources read:
- `data/outputs/2026-05-11_local_llama_gemma_controlled_v1/human_review/human_audit_all_200_normalized.csv`: 200 human review rows; normalized actions included 44 overrides and 8 excludes.
- `data/outputs/2026-05-11_local_llama_gemma_controlled_v1/human_adjusted/human_score_changes.csv`: 50 judge-score changes/exclusions after human review.

Observed historical Gemma/LLM-as-judge issue types from human review:

1. **R01 language over-strict false failure**: Gemma marked Korean responses as failed because of tiny English/typo fragments; human noted e.g. "한글자 틀렸다고 fail은 과하다".
2. **Semantic false pass on behavior/privacy/comparison/persona rules**: Gemma sometimes passed outputs that actually complied with the user's prohibited request, especially old R06 privacy, old R08 comparison, and subtle old R10 persona adoption.
3. **False failure when the triggering user request was absent or rule applicability was mismatched**: old R06 privacy was failed even when the user did not request private info.
4. **Persona false failure**: old R10 sometimes failed outputs even though the answer still maintained the required support/neutral perspective.
5. **Data/rule alignment exclusions**: 8 rows were excluded in the previous audit because input/rule-to-review mismatched.

Historical change counts by derived category:
{
  "R06_semantic_false_pass_under_detect": 13,
  "R08_semantic_false_pass_under_detect": 5,
  "R01_overstrict_minor_language_false_fail": 16,
  "old_data_rule_prompt_misalignment_exclude": 8,
  "R06_privacy_false_fail_when_no_private_info_request": 3,
  "R10_persona_false_pass_subtle_role_adoption": 1,
  "R10_persona_false_fail_official_perspective_kept": 4
}

Current-run mapping caveat:
- Current Q1 sampled cases include rules R01, R02, R03, R04, R05, R06, R07, R09, R10; **R08 is absent**, so the old R08 issue cannot be directly retested here.
- Current rule semantics differ from older controlled-v1 labels: current R04=privacy, current R06=ethics, current R07=complete requested artifact, current R10=neutral AI perspective.
- All current Q1 target attacks are against R03; Gemma judges mostly assess active filler/non-target rules, not the target R03 prefix rule.

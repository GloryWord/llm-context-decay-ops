# Integrated Q1 Gemma judge audit summary

## Data-run status

The Q1 sampled full run data is secured for analysis.

- Target model output file: `data/outputs/2026-05-18_q1_sampled_local_llama_gemma/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl`
- Final result SHA256 after metadata enrichment: `21d4e19dcffe2e4addf4ea7e0d5a1bf28b9fe520fdf1710e1c9fa28654329cf6`
- Target validation: 341/341 expected records and 2,852/2,852 expected turn results.
- Judge validation: 341 records complete, 2,852 turn results, 8,372 Gemma judge scores, unresolved judge scores = 0.
- Audit prep: 8,372 LLM/Gemma-judge score rows flattened; 1,140 candidate rows split into four shard reports.

## Audit reports

- `reports/worker-1-report.md`: R01/R04/R06 language/privacy/ethics shard; 193 shard rows, 36 directly reviewed, all 13 Gemma-false rows reviewed.
- `reports/worker-2-report.md`: R07 completeness shard; 527 rows reviewed.
- `reports/worker-3-report.md`: R09 uncertainty shard; 320 rows triaged/reviewed.
- `reports/worker-4-report.md`: R10 persona shard; 100 rows scanned, 50 manually reviewed.

## Reproduced or newly observed Gemma judge issues

### 1. R01 language over-strict false failures — reproduced

Worker-1 found seven R01 false failures where the answer was Korean-main and only contained tiny typo-like/foreign/conventional tokens. Examples: `row_id` 1413, 2221, 2241, 2467, 2507, 6638, 7040.

Interpretation: this reproduces the earlier human-labeling finding that Gemma/LLM judge can be too strict on Korean-language compliance when small English/foreign fragments appear.

### 2. Rule-trigger/applicability false failures — reproduced strongly

- R04 privacy/contact: worker-1 found six likely false failures where users asked for benign tips/records and the response only used generic placeholders or fields, not actual private/non-public contact data. Examples: `row_id` 732, 1236, 2560, 2765, 5745, 5905.
- R07 completeness: worker-2 found a large cluster: 304 of 447 Gemma-false R07 rows are likely applicability false failures on general tips/methods/advice prompts rather than requests for a complete artifact/full form.
- R09 uncertainty: worker-3 found a possible broader false-failure/overreach pattern where generic answer quality issues, repetition, or incompleteness were labeled as R09 uncertainty failures.

Interpretation: the old human-labeling problem “judge fails even though the triggering rule condition is absent/mismatched” clearly recurs, especially for R07 and some R04/R09 rows.

### 3. Semantic false pass / under-detection — partially reproduced

- R09: worker-3 found two suspected false passes, `row_id` 4627 and 5662, where the response appears to assert incorrect biblical facts without uncertainty, but Gemma passed.
- R04/R06: worker-1 did not find clear semantic false passes in reviewed true/NA samples.
- R10: worker-4 did not find semantic persona-adoption false passes in reviewed rows.

Interpretation: semantic under-detection exists in the current run, but the clearest evidence is R09 rather than the old R06/R08/R10 categories. R08 is not present in current Q1 and is not testable.

### 4. R10 applicability inconsistency — newly/related observed

Worker-4 found 35 R10 `judge_pass=True` rows where the user did not request a persona change and judge details often say no persona was requested. These likely should be NA/blank under the scorer contract, not True.

Interpretation: this does not reproduce the old subtle R10 persona-adoption miss, but it does show applicability handling inconsistency that can distort denominators/pass rates.

### 5. Data/rule alignment exclusions — not reproduced

Workers did not find the old “input/rule-to-review mismatched” exclusion issue in current shards. Current rows appear aligned with active `score_rule_id`/rule sets.

## Team lifecycle note

OMX team status shows one failed task (`task 1`) because a read-only subagent prematurely transitioned the lifecycle state to failed before worker-1 wrote the report. The actual worker-1 report exists and was later merged/verified. This is treated as an acknowledged orchestration-state issue, not an audit-work failure.

## Recommended analysis handling

1. Do not treat all Gemma-false rows as reliable human-equivalent failures without sensitivity checks.
2. For Q1 paper tables, separate at least these categories:
   - target R03 auto-prefix failures,
   - valid non-target failures,
   - suspected judge applicability false failures,
   - suspected semantic false passes.
3. For R07, consider re-scoring or excluding non-artifact general advice prompts from R07 denominators; worker-2 estimates 304 likely false failures.
4. For R10, decide and document whether non-triggered turns count as pass or NA; current Gemma behavior is inconsistent.
5. For final claims, cite this audit as evidence that Gemma judge remains useful for large-scale scoring but requires human-audit caveats and rule-specific post-processing.

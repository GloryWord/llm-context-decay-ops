# Worker-1 Q1 Target-Balanced Case/Provenance Validation Evidence

## Scope actually executed

Leader update received at `2026-05-19T14:32:31Z` via worker mailbox narrowed worker-1 scope: **do not start the full remote Llama/Gemma run**; worker-1 owns case/provenance generation validation only. This report follows that override.

## Generated artifacts

- `.tmp/q1_target_balanced_team/worker-1/q1_target_balanced_cases.jsonl`
- `.tmp/q1_target_balanced_team/worker-1/q1_target_balanced_cases_trace.csv`
- `.tmp/q1_target_balanced_team/worker-1/case_generation_summary.json`
- `.tmp/q1_target_balanced_team/worker-1/logs/generate_cases.log`
- `.tmp/q1_target_balanced_team/worker-1/logs/verify_*.log`

## Confirmed case/provenance facts

Source: `.tmp/q1_target_balanced_team/worker-1/case_generation_summary.json`

- Case count: `3069`
- Trace CSV rows: `3069`
- Target rules: `R01,R02,R03,R04,R05,R06,R07,R09,R10`
- Per-target distribution: `341` cases each
- Rule-count distribution: `1:99`, `3:990`, `5:990`, `7:990`
- Turn-count distribution: `1:558`, `5:837`, `10:837`, `15:837`
- Condition distribution: `benign_context:1116`, `injection_context:1953`
- Attack-order distribution: `none:1116`, `single_adversarial:279`, `implicit_then_adversarial:837`, `adversarial_then_implicit:837`
- R08 in rule sets: `false`
- R08 in system prompts: `false`
- JSONL SHA256: `027800333d09e6024083a0f264fc809977d70ea4aa8ce3fcb18b0d16edc26b5a`
- Trace SHA256: `dd98f70512e7187183eb212f75d89fe2d07724e2db72810f252179dd967b8071`
- Total target turn calls represented: `25668`
- Validation errors: `[]`

## Source files read and confirmed

- `AGENTS.md` — repository instruction requires evidence-first work and source reporting.
- `scripts/generate_q1_sampled_cases.py:42-58` — Q2 source CSV, default output, rule counts, turn counts, attack types, Q2 profile, default R03 target, seed, and sample cap.
- `scripts/generate_q1_sampled_cases.py:430-542` — `generate_q1_cases()` iterates selected target rules and rule counts, building benign and injection cases.
- `scripts/generate_q1_sampled_cases.py:876-955` — CLI supports `--all-target-rules`; main selects `profile["rule_ids"]` when set and validates/writes JSONL + trace CSV.
- `scripts/generate_q1_sampled_cases.py:865-873` — trace CSV writer emits one provenance row per generated case.
- `tests/test_generate_q1_sampled_cases.py:19-33` — tests assert Q2 final profile rule ids are exactly `R01,R02,R03,R04,R05,R06,R07,R09,R10`, R08 is absent, and each target has both attack prompts.
- `tests/test_generate_q1_sampled_cases.py:64-75` — tests assert default R03 count is 341 and R08 absent in cases/prompts.

Line snapshots are stored in:

- `.tmp/q1_target_balanced_team/worker-1/logs/source_line_refs_generate_q1.txt`
- `.tmp/q1_target_balanced_team/worker-1/logs/source_line_refs_tests_q1.txt`

## Commands run

```bash
.venv/bin/python scripts/generate_q1_sampled_cases.py \
  --all-target-rules \
  --output .tmp/q1_target_balanced_team/worker-1/q1_target_balanced_cases.jsonl \
  --trace-csv .tmp/q1_target_balanced_team/worker-1/q1_target_balanced_cases_trace.csv
```

```bash
.venv/bin/python -m py_compile \
  scripts/generate_q1_sampled_cases.py \
  scripts/run_experiment_fast.py \
  scripts/reaggregate_metrics.py
```

```bash
.venv/bin/python -m pytest tests/test_generate_q1_sampled_cases.py tests/test_run_experiment_fast_config.py -q
```

```bash
.venv/bin/python -m pytest -q
```

## Verification

- PASS — generation command produced `3069` cases and `3069` trace rows; log: `logs/generate_cases.log`.
- PASS — artifact validation summary has `validation_errors: []`; log: `logs/verify_artifact_summary.log`.
- PASS — py_compile for generator/runner/reaggregator; log: `logs/verify_py_compile.log`.
- PASS — targeted tests: `13 passed in 0.18s`; log: `logs/verify_targeted_pytest.log`.
- PASS — full test suite: `92 passed, 1 warning in 4.01s`; log: `logs/verify_full_pytest.log`.
- Linter note — no repo linter command/config was found or needed for worker-1 because no tracked Python source was edited; generated artifacts are JSONL/CSV/JSON/MD under `.tmp/q1_target_balanced_team/worker-1`.

## Risk / correction note

Before the leader update was processed, worker-1 briefly started a worker-scoped remote run. After the mailbox update was read, worker-1 stopped that duplicate run, deleted the partial output directory, and retained only `.tmp/q1_target_balanced_team/worker-1/aborted_duplicate_remote_run_note.json`. The validated worker-1 deliverable is only case/provenance generation evidence.

## Delegation compliance

Subagent spawn evidence: 2 child probes spawned (`019e40a6-6e98-7133-86f2-ace8d1244678` pipeline map, `019e40a6-80cd-75f0-be2d-b3b893b5c52c` rerun verification probe); both timed out without returning usable findings and were shut down, so final conclusions integrate local repo/file evidence listed above.

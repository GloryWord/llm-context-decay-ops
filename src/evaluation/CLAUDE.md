# evaluation module

## Role
Score model outputs against experiment case constraints, compute compliance metrics, and generate structured evaluation reports.

## Files
| File | Role |
|------|------|
| `evaluation.py` | Constraint scoring (18 IFEval types + multi-rule variants), aggregation by method/turn/rule/token_length |

## Scoring Approach

### v2: Project Aegis (primary)
- Per-rule programmatic scoring via `src/data_pipeline/generate_multi_rule_probes.score_rule(rule_id, response)`
- 10 auto-scoring functions (rules 1,2,3,4,5,8,11,14,16,20)
- Regex/string matching — no LLM judge needed

### Legacy: IFEval Constraint Scoring
- 18 constraint types in `CONSTRAINT_SCORERS` registry
- All-or-nothing: all constraints must pass for compliance=1

## Interface
```python
# evaluation.py
def score_response(response: str, scoring: dict) -> int: ...
def evaluate_results(results_dir: str, output_dir: str) -> dict: ...
```

## Aggregation Groups
- `compliance_by_method_and_turns` — compression method × turn_count
- `compliance_by_rule_count_and_turns` — rule_count_level × turn_count
- `compliance_by_rule_count_and_token_length` — rule_count_level × token_length
- `phase2_metrics` — defense effectiveness vs baseline (none)

## Report Paths
| Format | Path |
|--------|------|
| Summary JSON | `reports/evaluation_summary.json` |
| Scored records | `reports/scored_results.jsonl` |
| Figures | `reports/figures/*.png` |

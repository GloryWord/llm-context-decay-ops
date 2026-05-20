#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops"
cd "$ROOT"
OUTPUT_DIR="$ROOT/data/outputs/2026-05-18_q1_sampled_local_llama_gemma"
RESULT="$OUTPUT_DIR/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl"
ADJUSTED="$OUTPUT_DIR/ai_adjusted/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4_ai_adjusted.jsonl"
TRACE="$ROOT/data/processed/Research_Question_1_Data/q1_sampled_q2_injection_cases_trace.csv"
CASES="$ROOT/data/processed/q1_sampled_q2_injection_cases.jsonl"
AUDIT_SUMMARY="$ROOT/.tmp/q1_gemma_judge_audit/ai_labeling/ai_labeling_summary.json"
VIS_DIR="$OUTPUT_DIR/ai_adjusted/q1_visualization"
LOG_DIR="$OUTPUT_DIR/logs"
mkdir -p "$LOG_DIR"

log(){ printf '[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" | tee -a "$LOG_DIR/postprocess_all_target.log"; }

log "Applying Q1 AI judge audit policy"
.venv/bin/python scripts/apply_q1_ai_judge_audit.py \
  --input "$RESULT" \
  --output-dir "$OUTPUT_DIR/ai_adjusted" \
  --audit-dir "$ROOT/.tmp/q1_gemma_judge_audit/ai_labeling" \
  2>&1 | tee "$LOG_DIR/apply_q1_ai_judge_audit_all_target.log"

log "Reaggregating raw judged results"
.venv/bin/python scripts/reaggregate_metrics.py \
  --input "$RESULT" \
  --cases "$CASES" \
  --output-dir "$OUTPUT_DIR/reaggregated" \
  2>&1 | tee "$LOG_DIR/reaggregate_raw_all_target.log"

log "Reaggregating AI-adjusted judged results"
.venv/bin/python scripts/reaggregate_metrics.py \
  --input "$ADJUSTED" \
  --cases "$CASES" \
  --output-dir "$OUTPUT_DIR/ai_adjusted/reaggregated" \
  2>&1 | tee "$LOG_DIR/reaggregate_ai_adjusted_all_target.log"

log "Generating Q1 target-balanced visualizations"
.venv/bin/python scripts/plot_q1_sampled_visualizations.py \
  --input "$OUTPUT_DIR/ai_adjusted/reaggregated/metrics_enriched_results.jsonl" \
  --trace "$TRACE" \
  --judge-audit "$AUDIT_SUMMARY" \
  --output-dir "$VIS_DIR" \
  2>&1 | tee "$LOG_DIR/plot_q1_all_target.log"

log "Writing Q1 analysis report and presentation script"
.venv/bin/python scripts/write_q1_target_balanced_reports.py \
  --vis-dir "$VIS_DIR" \
  --manifest "$OUTPUT_DIR/run_manifest.json" \
  2>&1 | tee "$LOG_DIR/write_q1_reports_all_target.log"

log "Validating postprocess artifacts"
.venv/bin/python - <<'PY'
from pathlib import Path
import json, csv, collections, sys
root=Path('/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops')
out=root/'data/outputs/2026-05-18_q1_sampled_local_llama_gemma'
summary=json.loads((out/'ai_adjusted/q1_visualization/q1_visualization_summary.json').read_text(encoding='utf-8'))
audit=json.loads((root/'.tmp/q1_gemma_judge_audit/ai_labeling/ai_labeling_summary.json').read_text(encoding='utf-8'))
records=sum(1 for _ in (out/'ai_adjusted/reaggregated/metrics_enriched_results.jsonl').open(encoding='utf-8'))
target_csv=out/'ai_adjusted/q1_visualization/tables/q1_target_rule_final_turn_metrics.csv'
with target_csv.open(encoding='utf-8-sig', newline='') as f:
    target_rows=list(csv.DictReader(f))
required=[
 out/'ai_adjusted/q1_visualization/q1_analysis_report.md',
 out/'ai_adjusted/q1_visualization/q1_presentation_script.md',
 out/'ai_adjusted/q1_visualization/tables/q1_condition_final_turn_metrics.csv',
 target_csv,
 out/'ai_adjusted/q1_visualization/figures/q1_strict_success_by_rule_count_turn.png',
]
errors=[]
if records != 3069: errors.append(f'adjusted reaggregated records {records} != 3069')
if summary.get('records') != 3069: errors.append(f"summary records {summary.get('records')} != 3069")
if summary.get('target_rule_scope',{}).get('is_q2_available_target_balanced') is not True: errors.append('target scope not q2 target-balanced')
if audit.get('jsonl_records') != 3069: errors.append(f"audit jsonl_records {audit.get('jsonl_records')} != 3069")
if len(target_rows) != 9*4*4*2: errors.append(f'target_rule_csv rows {len(target_rows)} != 288')
missing=[str(p) for p in required if not p.exists() or p.stat().st_size==0]
if missing: errors.append('missing/empty: '+', '.join(missing))
print(json.dumps({
 'records': records,
 'summary_records': summary.get('records'),
 'target_scope': summary.get('target_rule_scope'),
 'audit_candidate_rows': audit.get('candidate_rows'),
 'audit_changed_score_cells': audit.get('changed_score_cells'),
 'target_rule_csv_rows': len(target_rows),
 'errors': errors,
}, ensure_ascii=False, indent=2))
if errors:
    sys.exit(41)
PY
log "Postprocess complete"

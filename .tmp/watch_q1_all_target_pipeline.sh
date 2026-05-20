#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops"
cd "$ROOT"
LOG="data/outputs/2026-05-18_q1_sampled_local_llama_gemma/logs/watch_all_target.log"
mkdir -p "$(dirname "$LOG")"
log(){ printf '[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" >> "$LOG"; }
while true; do
  if pgrep -f 'run_q1_all_target_llama_then_gemma.sh|run_experiment_fast.py --models vllm .*q1_sampled_q2_injection_cases|run_experiment_fast.py --judge-only .*fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl' >/dev/null; then
    log "main pipeline still running; watcher sleeping"
    sleep 300
    continue
  fi
  if python3 - <<'PY'
import json, pathlib, sys
root=pathlib.Path('/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops')
summary=root/'data/outputs/2026-05-18_q1_sampled_local_llama_gemma/ai_adjusted/q1_visualization/q1_visualization_summary.json'
if not summary.exists(): sys.exit(1)
d=json.loads(summary.read_text())
scope=d.get('target_rule_scope',{})
sys.exit(0 if d.get('records')==3069 and scope.get('is_q2_available_target_balanced') else 1)
PY
  then
    log "final visualization already complete; watcher exiting"
    exit 0
  fi
  log "main pipeline absent and final artifacts incomplete; invoking resume pipeline"
  TARGET_CONCURRENCY=12 JUDGE_CONCURRENCY=6 .tmp/resume_q1_all_target_pipeline.sh >> "$LOG" 2>&1 || log "resume pipeline failed; will retry"
  sleep 300
done

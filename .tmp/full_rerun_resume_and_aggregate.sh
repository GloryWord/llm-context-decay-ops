#!/usr/bin/env zsh
set -euo pipefail
cd /Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops
WATCH_PID="${1:-}"
if [[ -n "$WATCH_PID" ]]; then
  echo "[$(date '+%F %T %Z')] Waiting for active full-rerun PID $WATCH_PID"
  while kill -0 "$WATCH_PID" 2>/dev/null; do
    sleep 60
  done
fi
echo "[$(date '+%F %T %Z')] Active PID ended; running/resuming full rerun"
.venv/bin/python scripts/run_experiment_fast.py \
  --models vllm \
  --reps 5 \
  --concurrency 2 \
  --cases-file data/processed/experiment_cases_full.jsonl \
  --output-dir data/outputs/full_rerun_perfect_success

echo "[$(date '+%F %T %Z')] Reaggregating full rerun"
.venv/bin/python scripts/reaggregate_metrics.py \
  --input 'data/outputs/full_rerun_perfect_success/fast_results_*.jsonl' \
  --cases data/processed/experiment_cases_full.jsonl \
  --output-dir data/outputs/full_rerun_perfect_success/reaggregated

echo "[$(date '+%F %T %Z')] Done"

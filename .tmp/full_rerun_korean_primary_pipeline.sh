#!/usr/bin/env zsh
set -euo pipefail
cd /Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops

echo "[$(date '+%F %T %Z')] Starting full inference rerun with Korean-primary R01 judge placeholders"
.venv/bin/python scripts/run_experiment_fast.py \
  --models vllm \
  --reps 5 \
  --concurrency 2 \
  --cases-file data/processed/experiment_cases_full.jsonl \
  --output-dir data/outputs/full_rerun_perfect_success

echo "[$(date '+%F %T %Z')] Starting batch judge for behavioral + Korean-primary language rules"
.venv/bin/python scripts/run_experiment_fast.py \
  --judge-only \
  --input 'data/outputs/full_rerun_perfect_success/fast_results_*.jsonl' \
  --concurrency 10

echo "[$(date '+%F %T %Z')] Starting full reaggregation"
.venv/bin/python scripts/reaggregate_metrics.py \
  --input 'data/outputs/full_rerun_perfect_success/fast_results_*.jsonl' \
  --cases data/processed/experiment_cases_full.jsonl \
  --output-dir data/outputs/full_rerun_perfect_success/reaggregated

echo "[$(date '+%F %T %Z')] Full Korean-primary rerun pipeline complete"

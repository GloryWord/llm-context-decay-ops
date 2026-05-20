#!/usr/bin/env bash
set -euo pipefail
cd "/Users/kawai_tofu/Desktop/01_SeoulTech/SeoulTech_Local/Capstone_Design/Capstone_Dev/Codex-Multi-Agent-Workflow/llm-context-decay-ops"
LOG="data/outputs/2026-05-18_q1_sampled_local_llama_gemma/logs/judge_gemma_all_target_checkpointed_conc4_tmux_20260521_010651.log"
RESULT="data/outputs/2026-05-18_q1_sampled_local_llama_gemma/fast_results_hugging-quants_Meta-Llama-3.1-8B-Instruct-AWQ-INT4.jsonl"
{
  echo "[START] \2026-05-21 01:06:51 +0900"
  echo "[CONFIG] concurrency=4 checkpoint_every=1000 result=$RESULT"
  PYTHONPATH=.   JUDGE_PROVIDER=vllm   JUDGE_API_URL="http://210.179.28.26:18000/v1/chat/completions"   JUDGE_MODEL_NAME="cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"   JUDGE_CHECKPOINT_EVERY=1000   .venv/bin/python scripts/run_experiment_fast.py     --judge-only     --concurrency 4     --judge-checkpoint-every 1000     --input "$RESULT"
  status=$?
  echo "[END] \2026-05-21 01:06:51 +0900 status=$status"
  exit $status
} 2>&1 | tee -a "$LOG"

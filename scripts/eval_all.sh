#!/bin/bash
# eval_all.sh — Gemini + Cursor 동시 평가
#
# 두 평가자에게 병렬로 산출물을 보내고 결과를 수집.
# 하나가 실패해도 나머지는 진행.
#
# Usage:
#   bash scripts/eval_all.sh <deliverable_path>

set -uo pipefail

DELIVERABLE="${1:?Usage: eval_all.sh <deliverable_path>}"

if [ ! -f "$DELIVERABLE" ]; then
    echo "[eval-all] ERROR: File not found: $DELIVERABLE"
    exit 1
fi

echo "[eval-all] Starting parallel evaluation: $DELIVERABLE"
echo "[eval-all] Evaluators: Gemini (acpx) + Cursor (agent)"
echo ""

# Run both evaluators in parallel
bash scripts/eval_cycle.sh "$DELIVERABLE" &
PID_GEMINI=$!

bash scripts/eval_cursor.sh "$DELIVERABLE" &
PID_CURSOR=$!

# Wait for both
GEMINI_OK=0
CURSOR_OK=0

wait $PID_GEMINI && GEMINI_OK=1 || echo "[eval-all] Gemini evaluation failed (exit $?)"
wait $PID_CURSOR && CURSOR_OK=1 || echo "[eval-all] Cursor evaluation failed (exit $?)"

echo ""
echo "===== EVALUATION SUMMARY ====="
echo "  Gemini: $([ $GEMINI_OK -eq 1 ] && echo 'OK' || echo 'FAILED')"
echo "  Cursor: $([ $CURSOR_OK -eq 1 ] && echo 'OK' || echo 'FAILED')"
echo "  Results: docs/multi-agent-working-history/eval_*"
echo "==============================="

# At least one must succeed
if [ $GEMINI_OK -eq 0 ] && [ $CURSOR_OK -eq 0 ]; then
    echo "[eval-all] ERROR: Both evaluators failed. Do NOT proceed to next task."
    exit 1
fi

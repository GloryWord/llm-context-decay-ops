#!/bin/bash
# eval_all.sh — Gemini 오케스트레이터 기반 Cursor 평가 실행기
#
# [변경 이력]
#   기존: Claude Code(오케스트레이터) → Gemini(평가자1) + Cursor(평가자2) 병렬 실행
#   현재: Gemini(오케스트레이터) → Cursor Agent(평가자, Composer2 + GPT 모델) 실행
#
# Gemini는 오케스트레이터이므로 자기 자신을 평가자로 호출하지 않는다.
# 평가는 Cursor Agent만 담당한다.
#
# Usage:
#   bash scripts/gemini_only/eval_all.sh <deliverable_path>
#   bash scripts/gemini_only/eval_all.sh --final <deliverable_path>

set -uo pipefail

FINAL_FLAG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --final) FINAL_FLAG="--final"; shift ;;
        *) DELIVERABLE="$1"; shift ;;
    esac
done

DELIVERABLE="${DELIVERABLE:?Usage: eval_all.sh [--final] <deliverable_path>}"

if [ ! -f "$DELIVERABLE" ]; then
    echo "[eval-all] ERROR: File not found: $DELIVERABLE"
    exit 1
fi

echo "[eval-all] Gemini 오케스트레이터 → Cursor 평가 시작"
echo "[eval-all] Deliverable: $DELIVERABLE"
if [ -n "$FINAL_FLAG" ]; then
    echo "[eval-all] MODE: FINAL (GPT-5.4 Extra High 추가 검증 활성화)"
fi
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Cursor Agent 평가 실행 (Composer2 + GPT 병렬)
CURSOR_OK=0
bash "$SCRIPT_DIR/eval_cursor.sh" $FINAL_FLAG "$DELIVERABLE" && CURSOR_OK=1 || \
    echo "[eval-all] Cursor evaluation failed (exit $?)"

echo ""
echo "===== EVALUATION SUMMARY ====="
echo "  Orchestrator: Gemini (this instance)"
echo "  Cursor:       $([ $CURSOR_OK -eq 1 ] && echo 'OK' || echo 'FAILED')"
echo "  Results: docs/multi-agent-working-history/eval_cursor_*"
echo "==============================="

if [ $CURSOR_OK -eq 0 ]; then
    echo "[eval-all] ERROR: Cursor evaluation failed. Do NOT proceed to next task."
    exit 1
fi

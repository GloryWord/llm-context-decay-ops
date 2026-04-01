#!/bin/bash
# eval_cycle.sh — Gemini 오케스트레이터용 평가 사이클 래퍼
#
# [변경 이력]
#   기존: Claude Code(오케스트레이터)가 acpx를 통해 Gemini를 평가자로 호출
#   현재: Gemini가 오케스트레이터이므로, 이 스크립트는 Cursor 평가만 실행하는
#         eval_cursor.sh의 얇은 래퍼로 재정의된다.
#         (Gemini가 자기 자신을 acpx로 호출하는 무한루프를 방지)
#
# 자동 처리 항목:
#   - Cursor Agent(Composer2 + GPT) 평가 요청 → 결과 수신
#   - 결과 파일 저장
#
# Usage:
#   bash scripts/gemini_only/eval_cycle.sh <deliverable_path>
#   bash scripts/gemini_only/eval_cycle.sh --final <deliverable_path>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FINAL_FLAG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --final) FINAL_FLAG="--final"; shift ;;
        *) DELIVERABLE="$1"; shift ;;
    esac
done

DELIVERABLE="${DELIVERABLE:?Usage: eval_cycle.sh [--final] <deliverable_path>}"

if [ ! -f "$DELIVERABLE" ]; then
    echo "[eval] ERROR: File not found: $DELIVERABLE"
    exit 1
fi

echo "[eval] Gemini 오케스트레이터 → Cursor 평가 사이클 시작"
echo "[eval] Deliverable: $DELIVERABLE"
echo ""

# Gemini는 오케스트레이터이므로 acpx self-call 없이 Cursor만 실행
bash "$SCRIPT_DIR/eval_cursor.sh" $FINAL_FLAG "$DELIVERABLE"

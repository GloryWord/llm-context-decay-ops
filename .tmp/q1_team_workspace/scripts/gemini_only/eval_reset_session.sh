#!/bin/bash
# eval_reset_session.sh — Cursor Agent 세션 비상 리셋 (Gemini 오케스트레이터용)
#
# [변경 이력]
#   기존: Claude Code(오케스트레이터) → acpx Gemini 세션 리셋
#   현재: Gemini가 오케스트레이터이므로 acpx self-session 관리 불필요.
#         Cursor Agent는 agent -p (print mode) 기반으로 매 호출이 독립 세션이라
#         별도 리셋이 필요 없다.
#         이 스크립트는 Cursor Agent 환경 자체가 이상 동작할 때 사용하는 비상용이다.
#
# 사용법: bash scripts/gemini_only/eval_reset_session.sh

set -euo pipefail

echo "[eval-reset] Gemini 오케스트레이터 환경 — Cursor Agent 세션 리셋"
echo ""
echo "[eval-reset] Cursor Agent는 agent -p (print mode)로 매 호출이 독립 세션입니다."
echo "[eval-reset] 일반적으로 이 스크립트는 필요하지 않습니다."
echo ""
echo "[eval-reset] 비상 상황 가이드:"
echo "  1) Cursor Agent CLI(agent)가 응답 없을 경우 — Cursor IDE를 재시작하세요."
echo "  2) 모델 응답이 이상하거나 짧을 경우 — eval_cursor.sh가 자동으로 재시도합니다."
echo "  3) 임시 파일 정리가 필요할 경우 — 아래를 실행합니다."
echo ""

# 임시 counter 파일 정리 (기존 acpx 잔재)
COUNTER_FILE="/tmp/acpx_eval_turn_count"
if [ -f "$COUNTER_FILE" ]; then
    echo "[eval-reset] 구 acpx turn counter 파일 제거: $COUNTER_FILE"
    rm -f "$COUNTER_FILE"
fi

echo "[eval-reset] 정리 완료."
echo "[eval-reset] 다음 eval 실행 시 eval_cursor.sh를 정상적으로 실행하세요."

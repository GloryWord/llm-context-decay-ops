#!/bin/bash
# eval_reset_session.sh — evaluator 세션 수동 리셋 (비상용)
#
# 정상 운영에서는 eval_cycle.sh가 자동으로 리셋을 처리한다.
# 이 스크립트는 acpx가 비정상 상태일 때만 사용한다.
#
# 사용법: bash scripts/eval_reset_session.sh

set -euo pipefail

SESSION_NAME="evaluator"
COUNTER_FILE="/tmp/acpx_eval_turn_count"
ROLE_PROMPT="당신은 evaluator입니다. 산출물의 (1) 완결성, (2) 학문적 엄밀성, (3) 실행 가능한 이슈, (4) 주제가 산으로 가지 않는지, (5) 초기 문맥과 흐름을 잘 지켰는지를 한국어로 구조화하여 평가합니다. 각 항목을 상/중/하로 등급 매기고, 구체적인 개선 제안을 포함하세요."

echo "[eval] Closing existing session..."
acpx gemini sessions close "$SESSION_NAME" 2>/dev/null || true

echo "[eval] Creating fresh session..."
acpx gemini sessions new --name "$SESSION_NAME"
acpx --approve-all --timeout 60 gemini -s "$SESSION_NAME" "$ROLE_PROMPT"

echo "0" > "$COUNTER_FILE"
echo "[eval] Session reset complete. Turn counter reset to 0."

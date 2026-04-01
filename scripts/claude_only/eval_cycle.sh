#!/bin/bash
# eval_cycle.sh — Claude Code 오케스트레이터 전용: acpx 기반 Gemini 평가 사이클
#
# [사용 조건] Claude Code 플랜 구독 중일 때만 사용.
# Gemini 오케스트레이터 기간에는 scripts/gemini_only/ 를 사용하세요.
#
# 이 스크립트는 사용자가 직접 실행하지 않는다.
# Claude Code가 작업 완료 후 내부적으로 실행한다.
#
# 자동 처리 항목:
#   - evaluator 세션 생성 (없으면)
#   - 평가 요청 → 결과 수신
#   - Context 포화 감지 → 세션 자동 리셋 (15회 초과 or 응답 이상)
#   - 결과 파일 저장

set -euo pipefail

DELIVERABLE="${1:?Usage: eval_cycle.sh <deliverable_path>}"
SESSION_NAME="evaluator"
TIMEOUT=120
MAX_TURNS=15
COUNTER_FILE="/tmp/acpx_eval_turn_count"
ROLE_PROMPT="당신은 evaluator입니다. 산출물의 (1) 완결성, (2) 학문적 엄밀성, (3) 실행 가능한 이슈, (4) 주제가 산으로 가지 않는지, (5) 초기 문맥과 흐름을 잘 지켰는지를 한국어로 구조화하여 평가합니다. 각 항목을 상/중/하로 등급 매기고, 구체적인 개선 제안을 포함하세요."

# --- 함수 정의 ---

reset_session() {
    echo "[eval] Resetting evaluator session (reason: $1)..."
    acpx gemini sessions close "$SESSION_NAME" 2>/dev/null || true
    acpx gemini sessions new --name "$SESSION_NAME"
    acpx --approve-all --timeout 60 gemini -s "$SESSION_NAME" "$ROLE_PROMPT"
    echo "0" > "$COUNTER_FILE"
    echo "[eval] Session reset complete."
}

ensure_session() {
    if ! acpx gemini sessions list 2>/dev/null | grep -q "$SESSION_NAME"; then
        echo "[eval] Creating new evaluator session..."
        acpx gemini sessions new --name "$SESSION_NAME"
        acpx --approve-all --timeout 60 gemini -s "$SESSION_NAME" "$ROLE_PROMPT"
        echo "0" > "$COUNTER_FILE"
        echo "[eval] Evaluator session initialized."
    fi
}

get_turn_count() {
    if [ -f "$COUNTER_FILE" ]; then
        cat "$COUNTER_FILE"
    else
        echo "0"
    fi
}

increment_turn_count() {
    local count
    count=$(get_turn_count)
    echo $((count + 1)) > "$COUNTER_FILE"
}

# --- 메인 로직 ---

# 파일 존재 확인
if [ ! -f "$DELIVERABLE" ]; then
    echo "[eval] ERROR: File not found: $DELIVERABLE"
    exit 1
fi

# 1. 세션 확인/생성
ensure_session

# 2. Context 포화 감지 → 자동 리셋
TURN_COUNT=$(get_turn_count)
if [ "$TURN_COUNT" -ge "$MAX_TURNS" ]; then
    reset_session "turn count ${TURN_COUNT} >= ${MAX_TURNS}"
fi

# 3. 평가 요청
echo "[eval] Requesting evaluation for: $DELIVERABLE (turn $((TURN_COUNT + 1)))"
EVAL_RESULT=$(acpx --approve-all --timeout "$TIMEOUT" gemini -s "$SESSION_NAME" \
    "다음 작업물을 평가해주세요:

$(cat "$DELIVERABLE")" 2>&1) || true

# 4. 응답 이상 감지 → 세션 리셋 후 재시도
RESULT_LENGTH=${#EVAL_RESULT}
if [ "$RESULT_LENGTH" -lt 50 ]; then
    echo "[eval] Abnormal response detected (${RESULT_LENGTH} chars). Auto-resetting..."
    reset_session "abnormal response (${RESULT_LENGTH} chars)"

    echo "[eval] Retrying evaluation..."
    EVAL_RESULT=$(acpx --approve-all --timeout "$TIMEOUT" gemini -s "$SESSION_NAME" \
        "다음 작업물을 평가해주세요:

$(cat "$DELIVERABLE")" 2>&1) || true
fi

# 5. 턴 카운트 증가
increment_turn_count

# 6. 결과 출력
echo ""
echo "===== EVALUATION RESULT ====="
echo "$EVAL_RESULT"
echo "============================="

# 7. 결과를 파일로 저장
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BASENAME=$(basename "$DELIVERABLE" | sed 's/\.[^.]*$//')
RESULT_DIR="docs/multi-agent-working-history"
mkdir -p "$RESULT_DIR"
RESULT_FILE="${RESULT_DIR}/eval_${TIMESTAMP}_${BASENAME}.md"

cat > "$RESULT_FILE" << EOF
# Evaluation Result

- **Date**: $(date +%Y-%m-%d\ %H:%M)
- **Deliverable**: $DELIVERABLE
- **Evaluator**: Gemini (acpx session: $SESSION_NAME)
- **Session turn**: $(get_turn_count) / $MAX_TURNS

## Result

$EVAL_RESULT
EOF

echo ""
echo "[eval] Result saved to: $RESULT_FILE"

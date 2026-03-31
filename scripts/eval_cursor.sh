#!/bin/bash
# eval_cursor.sh — Cursor Agent (Composer2) 평가 스크립트
#
# Gemini eval_cycle.sh와 동일한 역할:
#   산출물을 Cursor Agent에 전달 → 평가 수신 → 결과 파일 저장
#
# Usage:
#   bash scripts/eval_cursor.sh <deliverable_path>
#
# Requirements:
#   - 'agent' CLI 설치 (Cursor AI)
#   - CURSOR_API_KEY 환경변수 또는 ~/.cursor 인증

set -euo pipefail

DELIVERABLE="${1:?Usage: eval_cursor.sh <deliverable_path>}"

if [ ! -f "$DELIVERABLE" ]; then
    echo "[cursor-eval] ERROR: File not found: $DELIVERABLE"
    exit 1
fi

ROLE_PROMPT="당신은 연구 산출물 검증자(verifier)입니다. 제출된 보고서의 (1) 데이터 정합성 (수치가 원본 JSON/코드와 일치하는지), (2) 논리적 일관성 (결론이 데이터에서 도출 가능한지), (3) 누락 사항, (4) 표현 오류를 한국어로 구조화하여 평가합니다. 각 항목을 상/중/하로 등급 매기고, 구체적인 수정 제안을 포함하세요."

echo "[cursor-eval] Evaluating: $DELIVERABLE"

EVAL_RESULT=$(agent -p "$(cat <<EOF
${ROLE_PROMPT}

다음 작업물을 평가해주세요:

$(cat "$DELIVERABLE")
EOF
)" 2>&1) || true

RESULT_LENGTH=${#EVAL_RESULT}
if [ "$RESULT_LENGTH" -lt 50 ]; then
    echo "[cursor-eval] WARNING: Short response (${RESULT_LENGTH} chars), may have failed"
fi

# Print result
echo ""
echo "===== CURSOR EVALUATION RESULT ====="
echo "$EVAL_RESULT"
echo "===================================="

# Save result
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BASENAME=$(basename "$DELIVERABLE" | sed 's/\.[^.]*$//')
RESULT_DIR="docs/multi-agent-working-history"
mkdir -p "$RESULT_DIR"
RESULT_FILE="${RESULT_DIR}/eval_cursor_${TIMESTAMP}_${BASENAME}.md"

cat > "$RESULT_FILE" << SAVEEOF
# Cursor Agent Evaluation Result

- **Date**: $(date +%Y-%m-%d\ %H:%M)
- **Deliverable**: $DELIVERABLE
- **Evaluator**: Cursor Agent (Composer2)

## Result

$EVAL_RESULT
SAVEEOF

echo ""
echo "[cursor-eval] Result saved to: $RESULT_FILE"

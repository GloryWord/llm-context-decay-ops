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

ROLE_PROMPT="당신은 코드 및 연구 산출물 검증자(verifier)입니다. 다음 6가지를 한국어로 구조화하여 평가합니다:
(1) 데이터 정합성: 보고서 수치가 원본 JSON/코드 출력과 일치하는지 직접 대조
(2) 코드 구조: 관련 스크립트(scripts/, src/)의 아키텍처, 모듈 분리, 중복 코드 여부
(3) 파이프라인 일관성: 케이스 생성 → 추론 → 채점 → 보고서 흐름에 누락/불일치가 없는지
(4) 논리적 일관성: 결론이 데이터에서 도출 가능한지, 과대 해석은 없는지
(5) 코드 품질: 에러 처리, 타입 힌트, 재현 가능성 (seed, checkpoint 등)
(6) 개선 제안: 리팩토링, 성능 최적화, 테스트 커버리지 등 구체적 제안
각 항목을 상/중/하로 등급 매기세요."

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

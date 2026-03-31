#!/bin/bash
# eval_cursor.sh — Cursor Agent 다중 모델 평가 스크립트
#
# 기본: Composer2 (코드/아키텍처) + Codex (low-level 정합성) 교차 검증
# 옵션: --final 시 Codex High로 최종 1회 검증 (고비용)
#
# Context 관리:
#   agent -p (print mode)는 매 호출이 독립 세션 — context 축적 없음.
#   대화형(agent) 사용 시 context 관리 명령:
#     /compact  — 대화 압축 (토큰 절약)
#     /clear    — 대화 초기화
#     /model    — 모델 전환
#
# Usage:
#   bash scripts/eval_cursor.sh <deliverable_path>              # 기본 (Composer2 + Codex)
#   bash scripts/eval_cursor.sh --final <deliverable_path>      # 최종 검증 (+ Codex High)
#   bash scripts/eval_cursor.sh --model composer-2 <deliverable>  # 특정 모델만

set -euo pipefail

# Parse arguments
FINAL_MODE=false
SPECIFIC_MODEL=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --final) FINAL_MODE=true; shift ;;
        --model) SPECIFIC_MODEL="$2"; shift 2 ;;
        *) DELIVERABLE="$1"; shift ;;
    esac
done

DELIVERABLE="${DELIVERABLE:?Usage: eval_cursor.sh [--final] [--model <model>] <deliverable_path>}"

if [ ! -f "$DELIVERABLE" ]; then
    echo "[cursor-eval] ERROR: File not found: $DELIVERABLE"
    exit 1
fi

RESULT_DIR="docs/multi-agent-working-history"
mkdir -p "$RESULT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BASENAME=$(basename "$DELIVERABLE" | sed 's/\.[^.]*$//')

# ============================================================
# Model-specific prompts
# ============================================================

PROMPT_COMPOSER2="당신은 코드 및 연구 산출물 검증자(verifier)입니다. 다음 6가지를 한국어로 구조화하여 평가합니다:
(1) 데이터 정합성: 보고서 수치가 원본 JSON/코드 출력과 일치하는지 직접 대조
(2) 코드 구조: 관련 스크립트(scripts/, src/)의 아키텍처, 모듈 분리, 중복 코드 여부
(3) 파이프라인 일관성: 케이스 생성 → 추론 → 채점 → 보고서 흐름에 누락/불일치가 없는지
(4) 논리적 일관성: 결론이 데이터에서 도출 가능한지, 과대 해석은 없는지
(5) 코드 품질: 에러 처리, 타입 힌트, 재현 가능성 (seed, checkpoint 등)
(6) 개선 제안: 리팩토링, 성능 최적화, 테스트 커버리지 등 구체적 제안
각 항목을 상/중/하로 등급 매기세요."

PROMPT_GPT54="당신은 연구 논리 검증자입니다. 다음을 검토합니다:
(1) 논리적 정합성: 연구 질문 → 실험 설계 → 결과 → 결론의 흐름이 논리적으로 일관되는지
(2) 수치-서술 일치: 본문의 서술이 표/그래프의 수치와 모순되지 않는지
(3) 과대 해석 여부: 데이터에서 도출 가능한 범위를 넘는 주장이 있는지
(4) 한계점 적절성: 실험 한계가 솔직하게 기술되었는지, 누락된 한계가 있는지
(5) 발표 준비도: 청중이 이해하기 어려운 용어, 비약, 누락된 설명이 있는지
각 항목을 상/중/하로 등급 매기세요. 한국어로 작성."

PROMPT_GPT54_FINAL="당신은 최종 검증자입니다. 논문/발표 제출 전 가장 높은 기준을 적용합니다:
(1) 수치 완전 검증: 보고서의 모든 수치가 표/그래프와 상호 일치하는지 전수 대조
(2) 논문 수준 엄밀성: 통계 용어 오용, 인과관계 과대 주장, 표본 크기 적절성
(3) 서술 일관성: 같은 수치가 다른 섹션에서 다르게 인용되지 않는지
(4) 시각화 정합성: 그래프 범례/축 라벨이 본문 설명과 일치하는지
(5) 발표 가독성: 비전공자가 핵심 메시지를 파악할 수 있는지, 오탈자
PASS/FAIL 판정과 함께 수정 필수 항목 목록을 작성하세요. 한국어로 작성."

# ============================================================
# Run evaluations
# ============================================================

run_eval() {
    local model="$1"
    local prompt="$2"
    local label="$3"

    echo "[cursor-eval] Running $label (model: $model)..."

    local result
    result=$(agent -p --model "$model" --trust "$(cat <<EOF
${prompt}

다음 작업물을 평가해주세요:

$(cat "$DELIVERABLE")
EOF
)" 2>&1) || true

    local result_length=${#result}
    if [ "$result_length" -lt 50 ]; then
        echo "[cursor-eval] WARNING: $label returned short response (${result_length} chars)"
        return 1
    fi

    # Save result
    local result_file="${RESULT_DIR}/eval_cursor_${label}_${TIMESTAMP}_${BASENAME}.md"
    cat > "$result_file" << SAVEEOF
# Cursor Agent Evaluation — ${label}

- **Date**: $(date +%Y-%m-%d\ %H:%M)
- **Deliverable**: $DELIVERABLE
- **Model**: $model
- **Role**: $label

## Result

$result
SAVEEOF

    echo "[cursor-eval] $label saved: $result_file"
    echo ""
    echo "===== $label RESULT ====="
    echo "$result"
    echo "========================="
    echo ""
    return 0
}

# Specific model mode
if [ -n "$SPECIFIC_MODEL" ]; then
    run_eval "$SPECIFIC_MODEL" "$PROMPT_COMPOSER2" "$SPECIFIC_MODEL"
    exit $?
fi

# Auto-select 1M variant if deliverable is large (>50KB)
FILE_SIZE=$(wc -c < "$DELIVERABLE" | tr -d ' ')
if [ "$FILE_SIZE" -gt 50000 ]; then
    GPT_MODEL="gpt-5.4-high"       # 1M context for large docs
    GPT_FINAL_MODEL="gpt-5.4-xhigh"
    echo "[cursor-eval] Large file (${FILE_SIZE} bytes) — using GPT-5.4 High / Extra High"
else
    GPT_MODEL="gpt-5.4-high"
    GPT_FINAL_MODEL="gpt-5.4-xhigh"
fi

# Default: Composer2 (코드) + GPT-5.4 (논리) parallel
echo "[cursor-eval] Starting evaluation: $DELIVERABLE"
echo "[cursor-eval] Models: composer-2 + ${GPT_MODEL}"
if $FINAL_MODE; then
    echo "[cursor-eval] FINAL MODE: +${GPT_FINAL_MODEL} (1회 최종 검증)"
fi
echo ""

COMPOSER2_OK=0
GPT_OK=0
GPT_FINAL_OK=0

run_eval "composer-2" "$PROMPT_COMPOSER2" "composer2" &
PID1=$!

run_eval "$GPT_MODEL" "$PROMPT_GPT54" "gpt54" &
PID2=$!

wait $PID1 && COMPOSER2_OK=1 || echo "[cursor-eval] Composer2 failed"
wait $PID2 && GPT_OK=1 || echo "[cursor-eval] GPT-5.4 failed"

# Final mode: GPT-5.4 Extra High (sequential, 1회만)
if $FINAL_MODE; then
    run_eval "$GPT_FINAL_MODEL" "$PROMPT_GPT54_FINAL" "gpt54-final"
    GPT_FINAL_OK=$?
fi

echo ""
echo "===== CURSOR EVALUATION SUMMARY ====="
echo "  Composer2:       $([ $COMPOSER2_OK -eq 1 ] && echo 'OK' || echo 'FAILED')"
echo "  GPT-5.4:         $([ $GPT_OK -eq 1 ] && echo 'OK' || echo 'FAILED')"
if $FINAL_MODE; then
    echo "  GPT-5.4 Final:   $([ $GPT_FINAL_OK -eq 0 ] && echo 'OK' || echo 'FAILED')"
fi
echo "  Results: ${RESULT_DIR}/eval_cursor_*_${TIMESTAMP}_*"
echo "======================================="

# At least one must succeed
if [ $COMPOSER2_OK -eq 0 ] && [ $GPT_OK -eq 0 ]; then
    exit 1
fi

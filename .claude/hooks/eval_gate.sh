#!/bin/bash
# eval_gate.sh — 평가 없이 다음 작업으로 넘어가지 못하도록 강제
#
# PostToolUse hook: Write/Edit 후 실행됨
# /tmp/pending_eval 파일이 존재하면 → 평가 미완료 경고
# eval_all.sh / eval_cycle.sh / eval_cursor.sh 실행 시 → 플래그 해제

PENDING_FILE="/tmp/pending_eval"

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)

# Write 또는 Edit 시 평가 대기 플래그 설정
if [ "$TOOL_NAME" = "Write" ] || [ "$TOOL_NAME" = "Edit" ]; then
    TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

    # docs/outputs/ 또는 src/ 하위 파일 수정 시 평가 필요 플래그
    if echo "$TOOL_INPUT" | grep -qE '(docs/outputs|src/|data/processed)'; then
        echo "$TOOL_INPUT" >> "$PENDING_FILE"
    fi
fi

# 평가 스크립트 실행 완료 시 플래그 해제 (eval_all, eval_cycle, eval_cursor 모두 인식)
if [ "$TOOL_NAME" = "Bash" ]; then
    TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
    if echo "$TOOL_INPUT" | grep -qE 'eval_(all|cycle|cursor)\.sh'; then
        rm -f "$PENDING_FILE"
    fi
fi

# 평가 대기 중인 파일이 있으면 경고
if [ -f "$PENDING_FILE" ]; then
    COUNT=$(wc -l < "$PENDING_FILE" | tr -d ' ')
    echo "[EVAL GATE] ${COUNT}개 산출물이 평가 대기 중. 반드시 bash scripts/eval_all.sh <산출물> 실행 필요." >&2
fi

exit 0

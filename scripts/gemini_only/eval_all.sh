#!/bin/bash
# eval_all.sh — ACPX Loop Controller for Professor-Feedback Revisions
#
# Usage:
#   bash scripts/gemini_only/eval_all.sh <packet.yaml> <TARGET_MD>
#
# Prerequisite:
#   Gemini (Orchestrator) must have already generated <packet.yaml> from feedback.

set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <packet.yaml> <TARGET_MD> [KEYWORD]"
    exit 1
fi

PACKET_YAML="$1"
TARGET_MD="$2"
KEYWORD="${3:-unnamed}"

if [[ ! -f "$PACKET_YAML" ]]; then
    echo "ERROR: packet not found: $PACKET_YAML"
    exit 1
fi

if [[ ! -f "$TARGET_MD" ]]; then
    echo "ERROR: Target document not found: $TARGET_MD"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACPX_PROMPTS_DIR="$(cd "$SCRIPT_DIR/../../docs/acpx_prompts" && pwd)"
BASE_RESULT_DIR="$(cd "$SCRIPT_DIR/../../docs/multi-agent-working-history" && pwd)"

# Organize result directory: DATE / TIME_KEYWORD
DATE_STR=$(date +%Y-%m-%d)
TIME_STR=$(date +%H%M%S)
RESULT_DIR="$BASE_RESULT_DIR/$DATE_STR/${TIME_STR}_$KEYWORD"
mkdir -p "$RESULT_DIR"

# Parse Route from packet.yaml (default to general)
ROUTE=$(grep '^route:' "$PACKET_YAML" | awk -F '"' '{print $2}' || echo "general")
if [[ -z "$ROUTE" || "$ROUTE" == "route:"* ]]; then
    ROUTE=$(grep '^route:' "$PACKET_YAML" | awk '{print $2}' || echo "general")
fi
ROUTE=${ROUTE:-general}

MAX_LOOPS=$(grep '^max_loops:' "$PACKET_YAML" | awk '{print $2}' || echo "2")

echo "[eval-all] Start ACPX Workflow"
echo "  Session Dir: $RESULT_DIR"
echo "  Route: $ROUTE"
echo "  Max Loops: $MAX_LOOPS"
echo "  Target: $TARGET_MD"
echo ""

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REVISED_MD_CURRENT="$RESULT_DIR/revised_current.md"
cp "$TARGET_MD" "$REVISED_MD_CURRENT"

NUMERIC_AUDIT_PARAM=""
BLOCKERS_PARAM=""
CURRENT_VERDICT=""

for (( loop=1; loop<=MAX_LOOPS; loop++ )); do
    echo "========================================="
    echo "   ACPX Execution Loop $loop / $MAX_LOOPS"
    echo "========================================="

    # 1. REVISER
    echo "[Loop $loop] Revising document via MJ_Codex..."
    TEMP_REVISER_OUT="$RESULT_DIR/reviser_raw_${TIMESTAMP}_L${loop}.txt"
    bash "$SCRIPT_DIR/acpx_mj_runner.sh" \
        --model "gpt-5.4" \
        --prompt-file "$ACPX_PROMPTS_DIR/REVISER_PROMPT.md" \
        --packet "$PACKET_YAML" \
        --doc "$TARGET_MD" \
        $BLOCKERS_PARAM \
        > "$TEMP_REVISER_OUT"

    # Extract Revised Document from the block
    python3 "$SCRIPT_DIR/extract_content.py" "$TEMP_REVISER_OUT" > "$REVISED_MD_CURRENT"

    # 2. NUMERIC AUDITOR (if route is numeric)
    NUMERIC_AUDIT_YAML="$RESULT_DIR/numeric_audit_${TIMESTAMP}_L${loop}.yaml"
    if [[ "$ROUTE" == "numeric" ]]; then
        echo "[Loop $loop] Numeric Auditing via MJ_Codex..."
        bash "$SCRIPT_DIR/acpx_mj_runner.sh" \
            --model "gpt-5.3-codex" \
            --prompt-file "$ACPX_PROMPTS_DIR/NUMERIC_AUDITOR_PROMPT.md" \
            --packet "$PACKET_YAML" \
            --revised "$REVISED_MD_CURRENT" \
            > "$NUMERIC_AUDIT_YAML"

        NUMERIC_AUDIT_PARAM="--numeric-audit $NUMERIC_AUDIT_YAML"
    else
        NUMERIC_AUDIT_PARAM=""
    fi

    # 3. FINAL VERIFIER
    echo "[Loop $loop] Final Verifying via Cursor AI..."
    CURRENT_VERDICT="$RESULT_DIR/verdict_${TIMESTAMP}_L${loop}.yaml"
    bash "$SCRIPT_DIR/acpx_cursor_runner.sh" \
        --model "gpt-5.4-high" \
        --prompt-file "$ACPX_PROMPTS_DIR/FINAL_VERIFIER_PROMPT.md" \
        --packet "$PACKET_YAML" \
        --revised "$REVISED_MD_CURRENT" \
        $NUMERIC_AUDIT_PARAM \
        $BLOCKERS_PARAM \
        --loop-index "$loop" \
        > "$CURRENT_VERDICT"

    # Check Result
    VERDICT_STATUS=$(grep '^VERDICT:' "$CURRENT_VERDICT" | awk '{print $2}' || echo "")
    if [[ -z "$VERDICT_STATUS" ]]; then
        # Fallback if the agent didn't format properly but has 'PASS'
        if grep -qi "PASS" "$CURRENT_VERDICT"; then VERDICT_STATUS="PASS"; else VERDICT_STATUS="BLOCK"; fi
    fi
    
    echo "[Loop $loop] Verdict: $VERDICT_STATUS"
    
    if [[ "$VERDICT_STATUS" == "PASS" ]]; then
        echo "✅ ACPX Loop Succeeded!"
        cp "$REVISED_MD_CURRENT" "$TARGET_MD"
        echo "Modifications applied to $TARGET_MD directly."
        exit 0
    else
        echo "❌ Blocks found in loop $loop."
        BLOCKERS_PARAM="--previous-blockers $CURRENT_VERDICT"
        if [[ $loop -eq $MAX_LOOPS ]]; then
            echo "🛑 Max loops reached ($MAX_LOOPS). ESCALATING TO HUMAN."
            echo "Failed to completely resolve professor feedback automatically."
            echo "Latest attempt is saved at $REVISED_MD_CURRENT"
            exit 1
        fi
        echo "Starting next loop with blockers..."
    fi
done

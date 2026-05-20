#!/bin/bash
# acpx_cursor_runner.sh — Final Verifier for ACPX Loop
#
# Usage:
#   bash acpx_cursor_runner.sh \
#       --model <gpt-5.4-high|gpt-5.4-extra-high> \
#       --prompt-file <path> \
#       --packet <packet.yaml> \
#       --revised <revised.md> \
#       [--numeric-audit <numeric_audit.yaml>] \
#       [--previous-blockers <verdict.yaml>] \
#       --loop-index <1|2>
#
# Output:
#   Stdout contains the VERDICT payload (usually redirect to verdict.yaml)

set -euo pipefail

MODEL="gpt-5.4-high"
PROMPT_FILE=""
PACKET_FILE=""
REVISED_FILE=""
NUMERIC_AUDIT_FILE=""
PREVIOUS_BLOCKERS_FILE=""
LOOP_INDEX="1"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model) MODEL="$2"; shift 2 ;;
        --prompt-file) PROMPT_FILE="$2"; shift 2 ;;
        --packet) PACKET_FILE="$2"; shift 2 ;;
        --revised) REVISED_FILE="$2"; shift 2 ;;
        --numeric-audit) NUMERIC_AUDIT_FILE="$2"; shift 2 ;;
        --previous-blockers) PREVIOUS_BLOCKERS_FILE="$2"; shift 2 ;;
        --loop-index) LOOP_INDEX="$2"; shift 2 ;;
        *) echo "Unknown option $1"; exit 1 ;;
    esac
done

if [[ -z "$PROMPT_FILE" || -z "$PACKET_FILE" || -z "$REVISED_FILE" ]]; then
    echo "ERROR: acpx_cursor_runner.sh missing required arguments." >&2
    exit 1
fi

if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "ERROR: Prompt file not found: $PROMPT_FILE" >&2
    exit 1
fi

# Build context for the AI
PROMPT_CONTENT=$(cat "$PROMPT_FILE")
PACKET_CONTENT=$(cat "$PACKET_FILE")
REVISED_CONTENT=$(cat "$REVISED_FILE")

# Optional contents
NUMERIC_CONTENT=""
if [[ -n "$NUMERIC_AUDIT_FILE" && -f "$NUMERIC_AUDIT_FILE" ]]; then
    NUMERIC_CONTENT=$(cat "$NUMERIC_AUDIT_FILE")
fi

BLOCKERS_CONTENT=""
if [[ -n "$PREVIOUS_BLOCKERS_FILE" && -f "$PREVIOUS_BLOCKERS_FILE" ]]; then
    BLOCKERS_CONTENT=$(cat "$PREVIOUS_BLOCKERS_FILE")
fi

# Create a temporary file for the full prompt to avoid argument too long
TMP_PROMPT=$(mktemp)

cat << EOF > "$TMP_PROMPT"
$PROMPT_CONTENT

--- 
## INPUT DATA

**LOOP_INDEX**: $LOOP_INDEX

### packet.yaml (Change Ledger & Original Context)
\`\`\`yaml
$PACKET_CONTENT
\`\`\`

### revised_document (The revision to evaluate)
\`\`\`markdown
$REVISED_CONTENT
\`\`\`
EOF

if [[ -n "$NUMERIC_CONTENT" ]]; then
    cat << EOF >> "$TMP_PROMPT"

### numeric_audit
\`\`\`yaml
$NUMERIC_CONTENT
\`\`\`
EOF
fi

if [[ -n "$BLOCKERS_CONTENT" ]]; then
    cat << EOF >> "$TMP_PROMPT"

### previous_blockers
\`\`\`yaml
$BLOCKERS_CONTENT
\`\`\`
EOF
fi

# Execute Cursor Agent
result=$(agent -p --model "$MODEL" --trust "$(cat "$TMP_PROMPT")" 2>&1 || true)
rm "$TMP_PROMPT"

echo "$result"

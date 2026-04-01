#!/bin/bash
# acpx_mj_runner.sh — MJ_Codex remote runner for Reviser/Numeric Auditor
#
# Usage:
#   bash acpx_mj_runner.sh \
#       --model <gpt-5.4|gpt-5.3-codex|...> \
#       --prompt-file <path> \
#       --packet <packet.yaml> \
#       [--doc <TARGET_MD>] \
#       [--revised <revised.md>] \
#       [--previous-blockers <verdict.yaml>]

set -euo pipefail

MJ_CODEX_USER="mhncity"
MJ_CODEX_IP="210.179.28.26"
MJ_CODEX_SESSION="codex-agent"

MODEL=""
PROMPT_FILE=""
PACKET_FILE=""
DOC_FILE=""
REVISED_FILE=""
PREVIOUS_BLOCKERS_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model) MODEL="$2"; shift 2 ;;
        --prompt-file) PROMPT_FILE="$2"; shift 2 ;;
        --packet) PACKET_FILE="$2"; shift 2 ;;
        --doc) DOC_FILE="$2"; shift 2 ;;
        --revised) REVISED_FILE="$2"; shift 2 ;;
        --previous-blockers) PREVIOUS_BLOCKERS_FILE="$2"; shift 2 ;;
        *) echo "Unknown option $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$MODEL" || -z "$PROMPT_FILE" || -z "$PACKET_FILE" ]]; then
    echo "ERROR: acpx_mj_runner.sh missing required arguments." >&2
    exit 1
fi

if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "ERROR: Prompt file not found: $PROMPT_FILE" >&2
    exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)_$RANDOM
TMP_PROMPT=$(mktemp)

cat "$PROMPT_FILE" > "$TMP_PROMPT"

cat << EOF >> "$TMP_PROMPT"

---
## INPUT DATA

### packet.yaml
\`\`\`yaml
$(cat "$PACKET_FILE")
\`\`\`
EOF

if [[ -n "$DOC_FILE" && -f "$DOC_FILE" ]]; then
    cat << EOF >> "$TMP_PROMPT"

### current_document ($DOC_FILE)
\`\`\`markdown
$(cat "$DOC_FILE")
\`\`\`
EOF
fi

if [[ -n "$REVISED_FILE" && -f "$REVISED_FILE" ]]; then
    cat << EOF >> "$TMP_PROMPT"

### revised_document ($REVISED_FILE)
\`\`\`markdown
$(cat "$REVISED_FILE")
\`\`\`
EOF
fi

if [[ -n "$PREVIOUS_BLOCKERS_FILE" && -f "$PREVIOUS_BLOCKERS_FILE" ]]; then
    cat << EOF >> "$TMP_PROMPT"

### previous_blockers
\`\`\`yaml
$(cat "$PREVIOUS_BLOCKERS_FILE")
\`\`\`
EOF
fi

REMOTE_FILE="/tmp/mj_prompt_${TIMESTAMP}.txt"

# Send prompt to remote server
scp -q "$TMP_PROMPT" "${MJ_CODEX_USER}@${MJ_CODEX_IP}:${REMOTE_FILE}"

# Execute MJ Codex via acpx
result=$(ssh -o BatchMode=yes "${MJ_CODEX_USER}@${MJ_CODEX_IP}" \
    "acpx --model ${MODEL} --format text codex -s ${MJ_CODEX_SESSION} exec -f ${REMOTE_FILE}" 2>&1) || true

# Cleanup
ssh -o BatchMode=yes "${MJ_CODEX_USER}@${MJ_CODEX_IP}" "rm -f ${REMOTE_FILE}" || true
rm "$TMP_PROMPT"

echo "$result"

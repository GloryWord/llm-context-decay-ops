#!/bin/bash
# test_mj_codex.sh — MJ_Codex (Remote Agent) 통신 테스트

REMOTE_USER="mhncity"
REMOTE_IP="210.179.28.26"
REMOTE_SESSION="codex-agent"

echo "[mj-codex-test] Connecting to MJ_Codex at ${REMOTE_USER}@${REMOTE_IP}..."

# SSH를 통해 원격지의 acpx를 호출하여 응답을 받아옵니다.
# --format text를 사용하여 순수 텍스트 결과만 추출합니다.
RESULT=$(ssh -o BatchMode=yes "${REMOTE_USER}@${REMOTE_IP}" \
    "acpx --format text codex -s ${REMOTE_SESSION} exec '안녕하세요 MJ_Codex님, Gemini 오케스트레이터입니다. 현재 작동 중인 환경의 호스트네임을 알려주세요.'" 2>&1)

if [ $? -eq 0 ]; then
    echo "[mj-codex-test] SUCCESS: Response received from MJ_Codex."
    echo ""
    echo "===== MJ_Codex RESPONSE ====="
    echo "$RESULT"
    echo "============================="
else
    echo "[mj-codex-test] ERROR: Connection failed."
    echo "Reason: $RESULT"
    echo "Check: SSH Key registration, Remote PC Status, and acpx session 'codex-agent'."
    exit 1
fi

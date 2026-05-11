#!/usr/bin/env bash
# eleva-restart-gateway.sh — restart OpenClaw gateway via systemctl --user.
# Verifies the service comes back active or exits non-zero with a pointer to journalctl.
set -u
source "$(dirname "$0")/env-detect.sh"

CMD='
  set -e
  export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"
  echo "Restarting openclaw-gateway..."
  systemctl --user restart openclaw-gateway
  sleep 3
  STATUS=$(systemctl --user is-active openclaw-gateway 2>/dev/null)
  echo "Service status: $STATUS"
  if [ "$STATUS" != "active" ]; then
    echo "ERROR: Gateway did not come back. Check journalctl --user -u openclaw-gateway -n 30."
    exit 1
  fi
  echo "Gateway restarted OK."
'

ssh eleva "$CMD"

#!/usr/bin/env bash
# eleva-status.sh — OpenClaw status: version + gateway service + group config + uptime on Eleva.
# Works on Mac (via ssh eleva) and on n8n VPS (via ssh eleva using the n8n→eleva bridge).
set -u
source "$(dirname "$0")/env-detect.sh"

CMD='
  export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"
  echo "=== OpenClaw version ==="
  openclaw --version 2>/dev/null || echo "(openclaw cmd not found)"
  echo
  echo "=== Gateway service ==="
  systemctl --user is-active openclaw-gateway 2>/dev/null || echo "(not active)"
  systemctl --user status openclaw-gateway --no-pager 2>/dev/null | head -5
  echo
  echo "=== Team group config ==="
  if [ -f ~/.openclaw/openclaw.json ]; then
    jq ".channels.telegram.groups.\"-1003974071850\"" ~/.openclaw/openclaw.json 2>/dev/null || echo "(jq missing or chat not configured)"
  fi
  echo
  echo "=== Uptime ==="
  uptime -p
'

ssh eleva "$CMD"

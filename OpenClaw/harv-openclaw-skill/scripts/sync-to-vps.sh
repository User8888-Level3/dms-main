#!/usr/bin/env bash
# sync-to-vps.sh — push the harv-openclaw-skill folder from Mac → n8n VPS.
# Manual / interactive use. The launchd-driven version lives at ~/.local/bin/sync-harv-openclaw-skill.sh
# (outside OneDrive — required for launchd to run it; see feedback-launchd-fda-onedrive.md).
set -u

SRC="$HOME/Library/CloudStorage/OneDrive-Personal/ClaudeCode/OpenClaw/harv-openclaw-skill/"
DST="n8n:~/workspaces/OpenClaw/harv-openclaw-skill/"
LOG="$HOME/Library/Logs/com.harv.openclaw-skill-sync.log"

mkdir -p "$(dirname "$LOG")"

echo "==== sync started $(date '+%Y-%m-%d %H:%M:%S') ====" >> "$LOG"

if ! ssh -o BatchMode=yes -o ConnectTimeout=5 n8n 'echo OK' >> "$LOG" 2>&1; then
  echo "WARN: SSH cold. Skipping sync." >> "$LOG"
  exit 0
fi

rsync -avz --delete \
  --exclude='.DS_Store' \
  --exclude='*.swp' \
  "$SRC" "$DST" >> "$LOG" 2>&1

RC=$?
echo "==== sync exit=$RC $(date '+%Y-%m-%d %H:%M:%S') ====" >> "$LOG"
exit $RC

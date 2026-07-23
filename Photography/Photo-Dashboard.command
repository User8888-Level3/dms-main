#!/bin/bash
# Double-click to open the Photo Archive dashboard in your browser.
#
# Double-click to open the Photo Archive dashboard. It runs photo_server.py in a
# foreground Terminal ON DEMAND. The background LaunchAgent was DISABLED 2026-06-27
# because Google Drive can't reliably serve files from a launchd background process
# ("Resource deadlock avoided"). Close the Terminal window to stop the server.

set -u
cd "$(dirname "$0")"

PORT=8765
URL="http://127.0.0.1:$PORT/"
AGENT_PLIST="$HOME/Library/LaunchAgents/com.harv.photo-archive.plist"

# Check whether the server is already responding
if curl -sS -o /dev/null -m 1.5 "$URL" 2>/dev/null; then
  echo "Photo Archive server already running. Opening browser…"
  open "$URL"
  exit 0
fi

echo "Photo Archive server not responding on $PORT — starting it in this window…"
# NOTE: intentionally does NOT touch the LaunchAgent (it's disabled — GDrive deadlock).

# Fallback: run the server right here so the dashboard still works.
if [ -d "/Volumes/Pictures-Vol3/.index/thumbs" ]; then
  :
else
  echo "WARNING: /Volumes/Pictures-Vol3 is not mounted."
  echo "Thumbs won't load and Open File/Open Folder buttons will fail."
  echo "Mount the Synology share first: Finder > Go > Connect to Server > smb://172.22.2.147/Pictures-Vol3"
  read -n 1 -s -r -p "Press any key to continue anyway, or Ctrl+C to quit..." || true
  echo
fi

echo "================================================"
echo " Photo Archive Dashboard (fallback mode)"
echo " URL: $URL"
echo " Close this window to stop the server."
echo "================================================"
( sleep 1.2 && open "$URL" ) &
PYBIN="/usr/local/bin/python3.13"
[ -x "$PYBIN" ] || PYBIN="./.venv/bin/python"
exec "$PYBIN" photo_server.py

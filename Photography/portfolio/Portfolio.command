#!/bin/bash
# Double-click to open the HARV BALU photo portfolio (local).
#
# Runs portfolio_app.server in a foreground Terminal ON DEMAND (same pattern as
# Photo-Dashboard.command — no LaunchAgent: Google Drive can't reliably serve
# files from a launchd background process). Close this window to stop the server.

set -u
cd "$(dirname "$0")"

PORT=8770
URL="http://127.0.0.1:$PORT/"
ADMIN_URL="http://127.0.0.1:$PORT/admin"

# Already running? Just open the browser.
if curl -sS -o /dev/null -m 1.5 "$URL" 2>/dev/null; then
  echo "Portfolio server already running. Opening browser…"
  open "$ADMIN_URL"
  exit 0
fi

# The originals + derivatives live on the NAS 'photo' share. macOS sometimes
# leaves a dead stub at /Volumes/photo and mounts at /Volumes/photo-1 — the
# app auto-detects that, so accept any readable candidate here.
MOUNT_OK=""
for M in /Volumes/photo /Volumes/photo-1 /Volumes/photo-2; do
  if ls "$M" >/dev/null 2>&1; then MOUNT_OK="$M"; break; fi
done
if [ -z "$MOUNT_OK" ]; then
  echo "WARNING: the NAS 'photo' share is not mounted (checked /Volumes/photo{,-1,-2})."
  echo "Photos and thumbnails will not load."
  echo "Mount it first: Finder > Go > Connect to Server > smb://172.22.2.147/photo"
  read -n 1 -s -r -p "Press any key to continue anyway, or Ctrl+C to quit..." || true
  echo
else
  echo "NAS share: $MOUNT_OK"
fi

echo "================================================"
echo " HARV BALU — Photo Portfolio"
echo " Site:  $URL"
echo " Admin: $ADMIN_URL"
echo " Close this window to stop the server."
echo "================================================"
( sleep 1.2 && open "$URL" ) &
PYBIN="/usr/local/bin/python3.13"
[ -x "$PYBIN" ] || PYBIN="../.venv/bin/python"
exec "$PYBIN" -m portfolio_app.server

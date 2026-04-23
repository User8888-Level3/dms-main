#!/bin/bash
# Double-click this file to launch the Photo Index dashboard.
# Starts a local HTTP server on port 8765 and opens the site in your default browser.
# Close this Terminal window (or Ctrl+C) to stop the server.

set -eu
cd "$(dirname "$0")"

PORT=8765
SITE_DIR="site"

# Kill any stale server from a prior run (ignore errors)
pkill -f "http.server $PORT" 2>/dev/null || true
sleep 0.5

# Verify venv
if [ ! -x ".venv/bin/python" ]; then
  echo "ERROR: Python venv not found at .venv/ — tell Claude to rebuild it."
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

# Verify SMB mount (thumbs live there)
if [ ! -d "/Volumes/Pictures-Vol3/.index/thumbs" ]; then
  echo "WARNING: /Volumes/Pictures-Vol3 is not mounted."
  echo "Thumbnails will not load. Mount the Synology share first (Finder > Go > Connect to Server > smb://172.22.2.147/Pictures-Vol3)."
  read -n 1 -s -r -p "Press any key to continue anyway, or Ctrl+C to quit..."
  echo
fi

URL="http://127.0.0.1:$PORT/"
echo "================================================"
echo " Photo Index Dashboard"
echo " URL: $URL"
echo " Keep this window open while browsing."
echo " Close this window (or Ctrl+C) to stop."
echo "================================================"
echo

# Open browser after a brief delay so the server has a moment to bind
( sleep 1.2 && open "$URL" ) &

# Run the server in the foreground so closing the window kills it
exec ./.venv/bin/python -m http.server "$PORT" --bind 127.0.0.1 --directory "$SITE_DIR"

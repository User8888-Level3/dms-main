#!/bin/bash
# Double-click to (re)index the /Volumes/photo share into the portfolio DB.
#
# Safe to run anytime: it is INCREMENTAL — already-indexed photos are skipped
# (matched on modified-time + size + existing thumbnails), so re-running after
# adding a few photos only processes the new ones. Your public/private and
# artwork choices are NEVER touched on re-index. Originals are only READ.
#
# Needs the imaging libraries, so it uses the project venv python (not system).

set -u
cd "$(dirname "$0")"

if [ ! -d "/Volumes/photo" ]; then
  echo "ERROR: /Volumes/photo is not mounted."
  echo "Mount it first: Finder > Go > Connect to Server > smb://172.22.2.147/photo"
  read -n 1 -s -r -p "Press any key to close..." || true
  exit 1
fi

PYBIN="../.venv/bin/python"
if [ ! -x "$PYBIN" ]; then
  echo "ERROR: project venv python missing ($PYBIN)."
  echo "Google Drive may have zeroed the venv symlink. Relink:"
  echo "  ln -sf /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 ../.venv/bin/python"
  read -n 1 -s -r -p "Press any key to close..." || true
  exit 1
fi

echo "================================================"
echo " HARV BALU — Portfolio re-index"
echo " Reading:  /Volumes/photo   (originals, read-only)"
echo " Writing:  /Volumes/photo/.portfolio  (thumbnails)"
echo "           + the local catalog DB"
echo "================================================"
exec "$PYBIN" -m portfolio_app.indexer --workers 8 "$@"

#!/usr/bin/env bash
# eleva-config-backup.sh — timestamp-stamped backup of OpenClaw config file before edit.
# Usage: eleva-config-backup.sh <relative-path-under-~/.openclaw>
# Default: openclaw.json
set -u
source "$(dirname "$0")/env-detect.sh"

REL_PATH="${1:-openclaw.json}"
TS=$(date +%Y%m%d-%H%M%S)

CMD="
  set -e
  SRC=\"\$HOME/.openclaw/$REL_PATH\"
  DST=\"\$SRC.bak.$TS\"
  if [ ! -f \"\$SRC\" ]; then
    echo \"ERROR: \$SRC not found\" >&2
    exit 1
  fi
  cp -p \"\$SRC\" \"\$DST\"
  echo \"Backup written: \$DST\"
  ls -la \"\$DST\"
"

ssh eleva "$CMD"

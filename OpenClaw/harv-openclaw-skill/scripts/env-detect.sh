#!/usr/bin/env bash
# env-detect.sh — single source of truth for Mac vs VPS detection.
# IDENTICAL to harv-hermes/scripts/env-detect.sh — same logic.
# Unlike harv-hermes, this skill does NOT set HERM_SSH_PREFIX — the TARGET is `ssh eleva`
# from BOTH Mac and the n8n VPS (the latter uses the n8n→eleva bridge keypair).
if [ -d "/Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal" ]; then
  export HERM_ENV="mac"
else
  export HERM_ENV="vps"
fi

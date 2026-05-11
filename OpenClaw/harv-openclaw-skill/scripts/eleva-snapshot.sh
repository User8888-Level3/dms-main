#!/usr/bin/env bash
# eleva-snapshot.sh — Hostinger API snapshot management for Eleva VPS.
# Modes: get (read current), create (POST new — REPLACES existing).
# Token lives in n8n/.env.secrets as HOSTINGER_API_TOKEN_ELEVA (per OpenClaw kb/CHANGELOG entry 2026-04-27).
# Mac-only — VPS does not have this token (intentional blast-radius reduction).
set -u
source "$(dirname "$0")/env-detect.sh"

ENV_FILE="$HOME/Library/CloudStorage/OneDrive-Personal/ClaudeCode/n8n/.env.secrets"
if [ "$HERM_ENV" = "vps" ]; then
  echo "ERROR: snapshot script requires Mac (env-file not synced to VPS)." >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found" >&2
  exit 1
fi

TOKEN=$(grep ^HOSTINGER_API_TOKEN_ELEVA= "$ENV_FILE" | cut -d= -f2-)
if [ -z "$TOKEN" ]; then
  echo "ERROR: HOSTINGER_API_TOKEN_ELEVA not found in $ENV_FILE" >&2
  exit 1
fi

VPS_ID="1379773"
API="https://developers.hostinger.com/api/vps/v1/virtual-machines/${VPS_ID}/snapshot"

MODE="${1:-get}"

case "$MODE" in
  get)
    curl -sS -H "Authorization: Bearer $TOKEN" "$API"
    echo
    ;;
  create)
    echo "Creating new snapshot (will REPLACE existing if any)..."
    curl -sS -X POST -H "Authorization: Bearer $TOKEN" "$API"
    echo
    ;;
  *)
    echo "Usage: $0 [get|create]" >&2
    exit 1
    ;;
esac

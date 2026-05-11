# harv-openclaw — OpenClaw operations skill

Manages OpenClaw on Eleva VPS from Mac and from n8n VPS.

**Canonical source:** this folder (`OneDrive-Personal/ClaudeCode/OpenClaw/harv-openclaw-skill/`).
**Mac access:** symlinked into `~/.claude/skills/harv-openclaw`.
**VPS access:** rsync'd to `~/workspaces/OpenClaw/harv-openclaw-skill/` on n8n, symlinked into VPS `~/.claude/skills/harv-openclaw`.

**Sync:** Mac → n8n VPS via launchd every 30 min, one-way. Manual push: `scripts/sync-to-vps.sh`.

**Design doc:** `../docs/plans/2026-05-10-harv-openclaw-skill-design.md`

See `SKILL.md` for capability sections and triggers.

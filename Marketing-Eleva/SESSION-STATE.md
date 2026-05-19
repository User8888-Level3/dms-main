# Session State — Marketing-Eleva Build

> **Read [PICKUP-2026-05-16.md](PICKUP-2026-05-16.md) first.** This file is the rolling operational state. PICKUP is the entry point.

## TL;DR — What's live

24/7 Marketing Claude Code session on Eleva VPS, with:
- Workspace bidirectionally synced Mac ↔ Google Drive ↔ Eleva (661 files / ~4.4 GB).
- rclone bisync every 5 min, offset by 2 min from Open House (`2-59/5` vs `*/5`).
- Two tmux sessions on Eleva: `claud-marketing` (REPL) + `claud-marketing-bot` (Telegram supervisor v2).
- @ElevaMarketing_bot accepting DMs from Harv only. **v2 (2026-05-16 evening): voice in + voice out** — Groq Whisper Large v3 Turbo STT, ElevenLabs Turbo v2.5 TTS with voice ID `uYXf8XasLslADfZ2MB4u`, ffmpeg for OGG/OPUS conversion.
- Sister workspace to OpenHouse-Eleva — shares OAuth infrastructure and skill sync.

## Phases — final status

| # | Phase | Status |
|---|---|---|
| 0 | Reuse Eleva snapshot `94416044` | ✅ |
| A | OneDrive → Google Drive upload | _in progress_ |
| B | Drive → Eleva bisync seed | pending |
| C | Bisync cron on Eleva | pending |
| D | Mac alias + tmux session | pending |
| E | @ElevaMarketing_bot via BotFather | pending |
| F | Bot supervisor scripts | pending |
| G | Round-trip + smoke-test verification | pending |
| H | Documentation | _this file is part of H_ |
| I | OneDrive cleanup reminders for 2026-05-25 | pending |

## How to use

```bash
# From any Mac terminal — attach to the persistent Marketing Claude session on Eleva
claude-marketing

# Detach (do NOT Ctrl-C):
# Ctrl-B then D

# DM Marketing assets bot from your phone:
# Open Telegram → @ElevaMarketing_bot → send a message
```

## Lessons learned during build

### macOS aggressive eviction of OneDrive Files-On-Demand

When pre-materializing 4.4 GB of OneDrive content via `find -exec cat`, macOS evicted materialized blocks back to cloud-only state mid-stream. Disk on-disk usage stayed at ~30 MB even after reading 134+ files. Workaround: skip pre-mat entirely, use `rclone copy` from the OneDrive Finder path — rclone holds files open during upload, dodging the eviction race. (Open House didn't hit this — Mac had more headroom at the time, or different OneDrive client version.)

### xargs `-I {}` command-line-length quirk

First pre-mat attempt used `xargs -0 -P 4 -I {} sh -c 'head -c 1 "$1"' _ {}`. xargs choked on the Social-Media subdir with `command line cannot be assembled, too long`. Likely an interaction between `-I` substitution and long pathnames with spaces. Avoided by switching strategy (see above).

## Bridge facts (Mac → Eleva)

- Eleva: `srv1379773.hstgr.cloud` (`2.24.29.70`)
- SSH: `eleva` alias (key-only, no TOTP from Mac)
- Tailscale fallback: `eleva-tailscale` (TOTP-gated, break-glass only)
- ControlPersist: 1h on both paths

## Files created/modified in this session

### Mac
- `~/.bashrc`, `~/.bash_profile` — added `claude-marketing` alias
- `~/Library/CloudStorage/GoogleDrive-harvinder.balu@gmail.com/My Drive/Marketing/` — new Drive folder (target of rclone copy from OneDrive)

### Eleva
- `~/.marketing/.env` (mode 600) — bot token + allowlist
- `~/.marketing/scripts/marketing-bisync.sh` — adapted from openhouse-bisync.sh
- `~/.marketing/scripts/marketing-bot.py` — adapted from openhouse-bot.py
- `~/.marketing/scripts/marketing-bot-loop.sh` — adapted from openhouse-bot-loop.sh
- `~/.marketing/bisync-filters.txt` (empty placeholder, extensible)
- `~/.marketing/logs/{bisync.log, bot.log, bot-loop.log}`
- `~/workspaces/Marketing/` (661 files)
- crontab: added `2-59/5 * * * *` marketing-bisync entry
- tmux: `claud-marketing` + `claud-marketing-bot`

### Build/ops workspace (`OneDrive-Personal/ClaudeCode/Marketing-Eleva/`)
- `docs/plans/2026-05-16-eleva-marketing-design.md`
- `docs/plans/2026-05-16-eleva-marketing-migration.md`
- `CLAUDE.md`
- `SESSION-STATE.md` (this file)
- `LAUNCH-LOG-2026-05-16-eleva-marketing.md`
- `PICKUP-2026-05-16.md`

### Memory
- `MEMORY.md` ★ entry under Active Projects
- `project-eleva-marketing-claude.md` (new topic file)
- Fixed stale `Marketing/ (268GB archive)` → `Marketing/ (4.4GB — migrated 2026-05-16)`

### Telegram
- New private @ElevaMarketing_bot via @BotFather, allowlist = Harv only

### Reminders (2026-05-25)
- macOS Reminder created
- Hermes cron job created

## Resume actions (next session)

None expected. If something feels off, run the verification gate from `docs/plans/2026-05-16-eleva-marketing-migration.md` (final section).

## Cross-references

- Sister workspace: `OpenHouse-Eleva/` (shipped earlier today, same pattern)
- Hem (Hermes Agent on n8n): `Hermes/` — separate VPS, separate bot
- Working marketing hub (not this archive): `Claude-Marketing/` — untouched

---

## Slack surface — SHIPPED 2026-05-18 PM

Bot now listens on **BOTH Telegram and Slack** via Socket Mode. Surface-agnostic core handles both. See memory `project-eleva-sisters-slack.md` for full architecture and `School-Broker-Eleva/docs/plans/2026-05-18-eleva-sisters-slack.md` for the implementation plan.

| Field | Value |
|---|---|
| Slack channel | `#eleva-marketing` |
| Channel ID | `C0B4MR6JDUJ` |
| Bot user ID | `U0B4FCMGR1R` |
| Slack app ID | `A0B4JBNFVEZ` |
| Slack workspace | HarvRealtor.com (`T09GWT09X0C`) |
| Allowlist | `U09GPA82345` (Harv only) |
| Telegram bot | @ElevaMarketing_bot (unchanged from v1) |
| Env vars added (mode 600) | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_CHANNEL_ID`, `SLACK_ALLOWED_USERS` |
| Bot code | refactored ~393 → ~531 lines; extracted `handle_message_core` + Slack adapter |
| Backup | `~/.marketing/scripts/marketing-bot.py.bak-v2-pretslack` |
| Slack lib | `slack-bolt 1.28.0` via `pip3 install --user --break-system-packages` on Eleva |
| Smoke verified | 2026-05-18 PM, text round-trip ✓ (slack RX → TX both directions) |

**Two gotchas surfaced during this ship (both documented in topic memory):**
1. **xapp- cross-wire silent fail** — Marketing initially had school's xapp- (same 98-char shape, no error log, bot connected to wrong app). Verify post-restart via slack-bolt DEBUG `connection_info.app_id`.
2. **`bot.log` vs `bot-loop.log` log split** — slack-bolt INFO/ERROR goes to `bot-loop.log` (via wrapper `>> "$LOG" 2>&1`), NOT `bot.log`. Tail both when debugging.

**Rollback (per-bot, isolated blast radius):**
```bash
ssh eleva 'cp ~/.marketing/scripts/marketing-bot.py.bak-v2-pretslack ~/.marketing/scripts/marketing-bot.py && \
  tmux send-keys -t claud-marketing-bot C-c; sleep 2; \
  tmux send-keys -t claud-marketing-bot "~/.marketing/scripts/marketing-bot-loop.sh" Enter'
```
Restores Telegram-only behavior; Slack channel sits empty without harm.

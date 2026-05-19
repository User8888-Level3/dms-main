# Session State — OpenHouse-Eleva Build

> 🚀 **NEXT SESSION PICKUP — read [`PICKUP-2026-05-16.md`](./PICKUP-2026-05-16.md) FIRST.** That's the canonical orientation doc with the decision tree, current operational state, things-not-to-do list, and likely next-session entry points.
>
> **Status (as of 2026-05-16 ~17:30 PT):** ✅ **FULLY SHIPPED + DOCUMENTED.** Eleva running 24/7 with persistent Claude Code session in tmux `claud-openhouse` and Telegram bot in tmux `claud-openhouse-bot`. Workspace bidirectionally synced with Mac via Google Drive under own HarvRealtor GCP OAuth client. Filter pattern for "Drive-only" files live. Skills synced. MS Graph verified. End-to-end Telegram smoke test passed.
>
> **For comprehensive detail (architecture, every config touched, troubleshooting, rollback):** see `LAUNCH-LOG-2026-05-16-eleva-openhouse.md`.

**Last updated:** 2026-05-16 ~22:35 PT (v2 voice + archive split + bisync re-baseline)
**Build duration:** ~4h 50min initial build + ~1h evening v2 work (voice + archive)
**Owner of build:** Mac Claude (Opus 4.7) with Harv
**Design doc:** `docs/plans/2026-05-16-eleva-openhouse-design.md`
**Canonical build log:** `LAUNCH-LOG-2026-05-16-eleva-openhouse.md`

## v2 (2026-05-16 evening) — voice + archive split

- **Bot v2:** voice in (Groq Whisper Large v3 Turbo) + voice out (ElevenLabs Turbo v2.5, voice ID `uYXf8XasLslADfZ2MB4u`). 1500-char TTS cap. ffmpeg installed on Eleva. Voice-in → voice-out, text-in → text-out. Bot v1 backed up at `~/.openhouse/scripts/openhouse-bot.py.bak-v1`.
- **Archive split:** 929 past-listing files moved into `Open House/Not-on-Mac-and-Eleva/` on Drive (Mac is stream-only there, no offline cache), then deleted from Eleva. Eleva now holds only the **105-file active set** (4780-Cabello-St + templates + workflow + CLAUDE.md). Drive cloud still has everything.
- **Bisync re-baselined** via `--resync` after the move. Was failing 19:00→22:21 PT with "too many deletes" safety abort (caused by the filter excluding the newly-moved 929 files vs the pre-move baseline). Fixed by mirroring the move on Eleva, deleting per design intent, then `--resync`.

---

## TL;DR — What's live

| Surface | State |
|---|---|
| Workspace (Mac, edit via Drive client) | `~/Library/CloudStorage/GoogleDrive-harvinder.balu@gmail.com/My Drive/Open House/` — 1034 files total, with `Not-on-Mac-and-Eleva/` set to stream-only (no offline cache) for the 929-file archive |
| Workspace (Eleva, where Claude reads/writes) | `~/workspaces/Open-House/` — **105 files / 148 MB active set only** (post-v2 reorg). Archive lives Drive-cloud-only. |
| Sync engine | rclone bisync, 5-min cron on Eleva (`*/5 * * * *`) |
| **OAuth client** | **Own HarvRealtor GCP project `423418041170`** (NOT rclone's shared default). Long-lived RTs (Production status). Bisync 2.3 sec under own quota (vs ~20 sec throttled). |
| **Filter file** | `eleva:~/.openhouse/bisync-filters.txt` — extensible. First rule: `- Not-on-Mac-and-Eleva/**`. Edit to add more "skip on Eleva" patterns. |
| Conflict policy | `--conflict-resolve=newer --conflict-loser=num` (newer wins; loser kept as `<name>.conflict-N`) |
| Mac alias to attach | `claude-openhouse` (SSH + tmux attach) |
| Claude Code | v2.1.143, Max-authed, tmux `claud-openhouse` cwd `~/workspaces/Open-House/` |
| Skills synced | `harv-realestate`, `harv-showcase`, `harv-email-drafter` (launchd timer, 30-min Mac → Eleva) |
| MS Graph | Verified — returns "Harv Balu / harvrealtor@outlook.com". RT auto-rotates atomically in `~/.openhouse/.env`. |
| Telegram surface | ✅ Live. New bot (separate from Hem) running in tmux `claud-openhouse-bot` on Eleva. Allowlist = `5883909804` (Harv only). Stateless `claude -p` per message. End-to-end tested with a real query at 13:58 PT (Claude correctly identified today's open house from workspace files, produced 2514-char operator briefing). |

## Phases — final status

| Phase | Description | Status |
|---|---|---|
| 0 | Eleva snapshot + pre-flight | ✅ Done (snapshot id `94416044` taken 2026-05-16 ~10:44 PT) |
| A | rsync OneDrive → Google Drive | ✅ Done (1032 files / 3.6 GB; required pre-materialization workaround) |
| B-prep | Install rclone 1.71.1 + OAuth + ship config | ✅ Done |
| C | Claude Code + Max auth + tmux | ✅ Done |
| D | Skill sync (launchd, 30 min) | ✅ Done |
| E | MS Graph RT bootstrap + auto-rotate | ✅ Done |
| B-finish | bisync --resync + 5-min cron | ✅ Done (Eleva seeded with 3.4 GB; cron `*/5 * * * *` active) |
| H | End-to-end sync verification | ✅ Done (Mac↔Eleva round-trip both directions, files converged at 1033 each side) |
| F | Telegram bot (new bot, separate from Hem) | ✅ DONE — bot live, allowlist set, end-to-end query test passed |

## How to use

```bash
# From any Mac terminal — attach to the persistent Claude session
source ~/.bash_profile     # only needed once per shell, if alias not loaded
claude-openhouse           # SSHes to Eleva, attaches to claud-openhouse tmux

# Detach (do NOT Ctrl-C):
# Ctrl-B then D

# Manual sync skills (rare — launchd does it every 30 min):
sync-openhouse-skills

# From your phone via Termius (or other SSH client):
ssh eleva -t "tmux attach -t claud-openhouse"
# (uses key auth; needs Synology VPN if office IP not allowlisted)
```

## Known issue — Mac → Eleva over public IP needs allowlisted source IP

Eleva's Hostinger firewall whitelists Harv's home ISP (`73.189.157.5`) and office (`50.196.138.2`). When Harv is on a different network without the Synology VPN active, `ssh eleva` to public IP `2.24.29.70:63988` times out. **Tailscale break-glass works** — `ssh eleva-tailscale` (Tailnet IP `100.69.229.124`) bypasses the firewall.

During this build I hit one timeout window and finished via Tailscale. If `claude-openhouse` ever times out, either:
1. Activate Synology VPN to exit through allowlisted home IP, OR
2. Replace the alias temporarily: `ssh eleva-tailscale -t "tmux attach -t claud-openhouse"`

## Critical discovery — OneDrive cloud-only files vs rsync

Documented in `memory/feedback-onedrive-prematerialize-before-rsync.md`. **TL;DR:** before bulk-copying out of OneDrive, force-materialize cloud-only files with `find . -type f -exec sh -c 'cat "$1" > /dev/null' sh {} \;` (parallelize with `xargs -P 8`). Otherwise rsync may hang at 99% CPU with no progress. We burned ~1 hour on this before discovering the fix.

## Bridge facts (Mac → Eleva)

| Field | Value |
|---|---|
| Mac SSH alias | `eleva` → `harvey@2.24.29.70:63988` (public, firewall-gated) |
| Mac SSH fallback | `eleva-tailscale` → `harvey@100.69.229.124:63988` (Tailnet, bypasses firewall) |
| Mac → Eleva auth | pubkey only (`~/.ssh/id_ed25519`), no TOTP |
| n8n → Eleva auth | publickey + TOTP (intentional 2FA gate, see `project-harv-openclaw-skill.md`) |
| Mac → n8n auth | **NEW 2026-05-16:** observed publickey + keyboard-interactive prompt. May be a recent hardening. Flag and investigate when needed. |

## Files created/modified in this session

| Path | Purpose |
|---|---|
| `OpenHouse-Eleva/CLAUDE.md` | Workspace primer |
| `OpenHouse-Eleva/SESSION-STATE.md` | THIS FILE |
| `OpenHouse-Eleva/LAUNCH-LOG-2026-05-16-eleva-openhouse.md` | **NEW** — comprehensive canonical build log |
| `OpenHouse-Eleva/docs/plans/2026-05-16-eleva-openhouse-design.md` | Design doc |
| `~/.local/bin/sync-openhouse-skills.sh` | Skill sync script |
| `~/Library/LaunchAgents/com.harv.openhouse-skill-sync.plist` | launchd timer (30 min) |
| `eleva:~/.openhouse/.env` | MS Graph creds + Telegram bot token (mode 600) |
| `eleva:~/.openhouse/scripts/refresh-rt.py` | Token refresh + auto-rotate-in-place |
| `eleva:~/.openhouse/scripts/openhouse-bisync.sh` | rclone bisync wrapper (flock-guarded, throttled, **uses --filter-from**) |
| `eleva:~/.openhouse/scripts/openhouse-bot.py` | Telegram bot polling loop |
| `eleva:~/.openhouse/scripts/openhouse-bot-loop.sh` | Bot supervisor (auto-restart) |
| `eleva:~/.openhouse/bisync-filters.txt` | **NEW** — rclone filter rules; extensible |
| `eleva:~/.config/rclone/rclone.conf` | Google Drive OAuth config — now using **own HarvRealtor client_id** |
| `eleva:~/.config/rclone/rclone.conf.bak-20260516-152156` | **NEW** — backup of pre-own-client_id config |
| `eleva` crontab | `*/5 * * * *` openhouse-bisync.sh |
| Mac `~/.bashrc` + `~/.bash_profile` | Added `claude-openhouse` and `sync-openhouse-skills` aliases |
| Mac `~/.config/rclone/rclone.conf` | Now using **own HarvRealtor client_id** |

## Memory updates this session

- ★ New MEMORY.md index entry: "Eleva Open House Claude — BUILT 2026-05-16" (in Active Projects section)
- New topic file: `memory/project-eleva-openhouse-claude.md`
- New feedback file: `memory/feedback-onedrive-prematerialize-before-rsync.md` — captures the materialization workaround

## Post-ship optimizations (15:00-15:35 PT)

### Own Google Cloud OAuth client (HarvRealtor project)

Switched off rclone's shared default Google Cloud project to Harv's own. Steps taken:

1. Created OAuth client `rclone-gdrive-eleva-VPS051626` in **HarvRealtor** project (project number `423418041170`).
2. Application type: **Desktop app** (auto-handles `http://127.0.0.1:53682/` callback — no need to explicitly register redirect URI).
3. Enabled Google Drive API in HarvRealtor.
4. Published OAuth consent screen to **"In production"** (NOT Testing — critical because Testing mode gives 7-day refresh tokens, Production gives long-lived).
5. Added `harvinder.balu@gmail.com` as Test User (still required even in Production for unverified apps).
6. Mac `~/.config/rclone/rclone.conf` updated with new `client_id` and `client_secret`.
7. OAuth dance triggered, browser flow completed, token saved.
8. Mac config SCP'd to Eleva (old preserved as `~/.config/rclone/rclone.conf.bak-20260516-152156`).
9. Bisync verified: **2.3 sec** under own quota (vs ~20 sec under shared throttled project).

**What this buys:**
- 1 billion API queries/day for HarvRealtor alone (vs rclone's shared per-minute burst quota)
- Long-lived refresh tokens (no 7-day re-auth)
- Clean ownership — HarvRealtor project owns OAuth client + Drive API + consent screen

**Trade-off accepted:** Unverified app — during OAuth, Google shows "Google hasn't verified this app" warning. Click "Advanced" → "Go to HarvRealtor rclone (unsafe)" → Allow. One-time per OAuth flow.

### Bisync filter pattern for "Drive-only" files

Harv created `Open House/Not-on-Mac-and-Eleva/` as a drop zone for files that should live in Google Drive cloud only — not in Mac local copy (beyond stubs), not on Eleva at all.

Wired up filter support:

- `eleva:~/.openhouse/bisync-filters.txt` — rclone filter rules file
- First rule: `- Not-on-Mac-and-Eleva/**` (excludes contents)
- `openhouse-bisync.sh` updated to use `--filter-from <FILTERS>`
- Extensible — Harv can edit the filter file anytime, no script change needed

**Mac side:** Drive Desktop default Stream mode keeps files as stubs (4 KB each) unless actively opened. Right-click in Finder → "Online only" makes specific files explicitly cloud-only. The folder shell does appear on Eleva (4 KB empty dir) but contents never sync.

**To add more "no-sync" patterns:**
```bash
ssh eleva-tailscale 'nano ~/.openhouse/bisync-filters.txt'
# Add lines like: - _archive/**  or  - **/*.heic
# Save. Next cron picks it up.
```

## Phase F implementation (Telegram bot)

**Decision recap:** Harv considered Hem bridge first (~60-90 min, one-bot UX) vs new bot (~20 min, two-bot UX). Chose **new bot** for simplicity and isolation, accepting two-bot UX.

**Bot architecture:**
- New Telegram bot created via @BotFather (Harv-owned).
- Polling script `~/.openhouse/scripts/openhouse-bot.py` — raw urllib, no external deps. Long-polls `getUpdates` with `offset` tracking.
- Supervisor `~/.openhouse/scripts/openhouse-bot-loop.sh` — `while true; do python3 bot.py; sleep 5; done` for auto-restart.
- Runs in tmux session `claud-openhouse-bot` (separate from `claud-openhouse` Claude Code session).
- Stateless: each Telegram message → fresh `claude -p` subprocess with `cwd=~/workspaces/Open-House`. No multi-turn memory between messages.
- Allowlist: only Harv (`5883909804`). Other senders silently ignored.
- Built-in commands: `/start`, `/help`, `/status`. Anything else → Claude.
- Reply chunking: Telegram's 4096-char limit → bot splits on word/newline boundaries.
- Timeouts: Claude call has 600s wall-clock cap. Telegram long-poll has 60s.

**Env additions (in `~/.openhouse/.env` mode 600):**
```
TELEGRAM_BOT_TOKEN=<46-char BotFather token>
TELEGRAM_ALLOWED_USERS=5883909804
OPENHOUSE_WORKDIR=/home/harvey/workspaces/Open-House
```

**Smoke test 2026-05-16 13:58 PT:** Harv DMed *"Tell me about the property that I'm doing the open house for today"*. Bot replied in 32 sec with a 2514-char comprehensive briefing on 4780 Cabello St — pulled from workspace docs (price, MLS#, 9 buyer Q&A flags, listing-agent attribution, Harv's voice rules including "no em dashes," marketing-asset filenames). Claude correctly identified today's property from `4780-Cabello-Open-House-Workspace.md` filename + mtimes. End-to-end PASS.

**Known limitations / future improvements:**
- **Stateless** — no multi-turn. Future: use `claude --resume <session-id>` keyed by chat_id.
- **Reply content not logged** (intentional, to keep operational data out of `~/.openhouse/logs/bot.log`). Future: add an optional `BOT_LOG_REPLIES=1` flag for debugging windows.
- **No date-context prefix** — Claude inferred "today" from workspace files. Works for now; consider injecting `Today is YYYY-MM-DD (Day-of-week).` for sturdier behavior across queries that need calendar awareness.

## What I did NOT do

- **OneNote update:** Computers notebook → Open House Claude entry. Recommended but not done.
- **Memory consolidation:** the index entry is in place but full triage of MEMORY.md size (now 343 lines) is its own task.
- **Delete OneDrive copy of Open House:** kept as backup at `~/Library/CloudStorage/OneDrive-Personal/Open House/`. Recommend keeping for 1 week, then delete.
- **Mac → n8n TOTP investigation:** observed during this session but not investigated. Future session task.
- **Create our own Google API client_id** to bypass shared-project rate limits. Not blocking now (throttled bisync works within quota), but would speed up large operations.
- **Bot persistence across Eleva reboots:** currently tmux-only. If Eleva reboots, the bot won't auto-restart (tmux dies on reboot, even with linger on the user). Future: systemd user unit for `claud-openhouse-bot` (mirror OpenClaw gateway pattern).

## Resume actions (next session)

1. Confirm bisync cron is firing cleanly: `ssh eleva 'tail -20 ~/.openhouse/logs/bisync.log'` — expect "==== bisync exit=0 ====" every 5 min.
2. Decide whether to ship Phase F (Telegram) and pick approach (Hem bridge vs new bot).
3. Consider OneNote entry for Computers notebook.
4. Validate skills work end-to-end inside the Eleva Claude Code session:
   - `claude-openhouse` → "/realestate-quick 4780 Cabello St" or similar
   - "Read my latest Outlook inbox" (exercises MS Graph)

## Cross-references

- Hem (sister workspace) — `OneDrive-Personal/ClaudeCode/Hermes/PICKUP-2026-05-14.md`
- OpenClaw (co-tenant on Eleva) — `OneDrive-Personal/ClaudeCode/OpenClaw/PICKUP-2026-05-11.md`
- harv-openclaw skill — `~/.claude/skills/harv-openclaw/SKILL.md` (still operational, untouched)
- Memory: `~/.claude/projects/.../memory/project-eleva-openhouse-claude.md`

---

*Final write-up by Mac Claude at 2026-05-16 ~13:25 PT after full ship + verification. Update or supersede with each meaningful state change.*

---

## Slack surface — SHIPPED 2026-05-18 PM

Bot now listens on **BOTH Telegram and Slack** via Socket Mode. Surface-agnostic core handles both. See memory `project-eleva-sisters-slack.md` for full architecture and `School-Broker-Eleva/docs/plans/2026-05-18-eleva-sisters-slack.md` for the implementation plan.

| Field | Value |
|---|---|
| Slack channel | `#eleva-openhouse` |
| Channel ID | `C0B5GLY1HL0` |
| Bot user ID | `U0B4Q7545H7` |
| Slack app ID | `A0B4G1FNKSP` |
| Slack workspace | HarvRealtor.com (`T09GWT09X0C`) |
| Allowlist | `U09GPA82345` (Harv only) |
| Telegram bot | (open-house TG bot) (unchanged from v1) |
| Env vars added (mode 600) | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_CHANNEL_ID`, `SLACK_ALLOWED_USERS` |
| Bot code | refactored ~393 → ~531 lines; extracted `handle_message_core` + Slack adapter |
| Backup | `~/.openhouse/scripts/openhouse-bot.py.bak-v2-pretslack` |
| Slack lib | `slack-bolt 1.28.0` via `pip3 install --user --break-system-packages` on Eleva |
| Smoke verified | 2026-05-18 PM, text round-trip ✓ (slack RX → TX both directions) |

**Two gotchas surfaced during this ship (both documented in topic memory):**
1. **xapp- cross-wire silent fail** — Marketing initially had school's xapp- (same 98-char shape, no error log, bot connected to wrong app). Verify post-restart via slack-bolt DEBUG `connection_info.app_id`.
2. **`bot.log` vs `bot-loop.log` log split** — slack-bolt INFO/ERROR goes to `bot-loop.log` (via wrapper `>> "$LOG" 2>&1`), NOT `bot.log`. Tail both when debugging.

**Rollback (per-bot, isolated blast radius):**
```bash
ssh eleva 'cp ~/.openhouse/scripts/openhouse-bot.py.bak-v2-pretslack ~/.openhouse/scripts/openhouse-bot.py && \
  tmux send-keys -t claud-openhouse-bot C-c; sleep 2; \
  tmux send-keys -t claud-openhouse-bot "~/.openhouse/scripts/openhouse-bot-loop.sh" Enter'
```
Restores Telegram-only behavior; Slack channel sits empty without harm.

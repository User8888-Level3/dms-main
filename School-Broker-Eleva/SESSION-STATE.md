# School-Broker-Eleva — Session State

**Last verified:** 2026-05-18 09:00 PT — **SHIPPED ✅**

> For comprehensive handoff, read `SESSION-CONTINUATION-2026-05-18.md` (this folder).

## Where things stand

| Phase | Status |
|---|---|
| 0–E (snapshot, copy, scripts, env, alias) | ✅ done |
| F (Harv → BotFather → @Eleva_RE_School_bot) | ✅ token landed via secure terminal-paste pattern |
| G (tmux claud-school + claud-school-bot) | ✅ both running, bot PID 248365 polling |
| H (smoke test) | ✅ text + voice both confirmed by Harv at 08:45 + 08:54 |
| I (bisync --resync baseline) | ✅ exit=0 at 08:00:13 |
| J (cron offset 1) | ✅ added |
| K (verification bisync) | ✅ exit=0 at 08:00:58 |
| L (macOS Reminder 2026-05-27) | ✅ set |
| M (workspace-side CLAUDE.md + _workflow/onboarding) | ✅ synced to Eleva |
| N (Mac build/ops docs) | ✅ all 6 files written (incl. SESSION-CONTINUATION) |
| O (memory updates) | ✅ ★ entry + topic file + new secret-transfer feedback memory |
| P (OneNote page) | ✅ created → clobbered by bad PATCH → restored with full content |
| Q (Telegram ship-complete ping) | ✅ msg id 10, 405 chars delivered |
| Extra: 3-way sync verification (Harv-requested) | ✅ MD5-verified across Drive + Mac + Eleva |

## Live config

| Field | Value |
|---|---|
| Eleva | `srv1379773` Hostinger Ubuntu 24.04, alias `eleva` |
| Snapshot | `94416044` (shared, expires 2026-06-05) |
| Workspace path (Eleva) | `~/workspaces/School-Broker/` |
| File count (Drive/Mac/Eleva) | 18 / 18 / 18 ✅ |
| Bytes (Drive/Eleva) | 189138816 / 189138816 ✅ MD5 verified |
| Cron offset | `1-59/5` (school-bisync.sh) |
| Mac alias | `claude-school` |
| Tmux REPL session | `claud-school` (active) |
| Tmux bot supervisor | `claud-school-bot` (active) |
| Bot | `@Eleva_RE_School_bot` (id 8925136556, display "Eleva RE School") |
| Bot env file | `~/.school/.env` (mode 600) |
| Last smoke test activity | RX VOICE + TX VOICE 08:54 PT |
| Ship ping | msg id 10 at ~08:59 PT |

## Next action

**None.** Workspace is fully operational. Harv can:
- Run `claude-school` from Mac terminal for tmux REPL
- DM `@Eleva_RE_School_bot` on Telegram from anywhere (text or voice)
- Edit study notes on Mac via Drive client — bisync picks them up within 5 min

For ongoing maintenance see Decision Tree in `SESSION-CONTINUATION-2026-05-18.md`.

---

## Slack surface — SHIPPED 2026-05-18 PM

Bot now listens on **BOTH Telegram and Slack** via Socket Mode. Surface-agnostic core handles both. See memory `project-eleva-sisters-slack.md` for full architecture and `School-Broker-Eleva/docs/plans/2026-05-18-eleva-sisters-slack.md` for the implementation plan.

| Field | Value |
|---|---|
| Slack channel | `#eleva-school` |
| Channel ID | `C0B4HQU7XSR` |
| Bot user ID | `U0B4ETXJZ8T` |
| Slack app ID | `A0B4P11AA65` |
| Slack workspace | HarvRealtor.com (`T09GWT09X0C`) |
| Allowlist | `U09GPA82345` (Harv only) |
| Telegram bot | @Eleva_RE_School_bot (unchanged from v1) |
| Env vars added (mode 600) | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_CHANNEL_ID`, `SLACK_ALLOWED_USERS` |
| Bot code | refactored ~393 → ~531 lines; extracted `handle_message_core` + Slack adapter |
| Backup | `~/.school/scripts/school-bot.py.bak-v2-pretslack` |
| Slack lib | `slack-bolt 1.28.0` via `pip3 install --user --break-system-packages` on Eleva |
| Smoke verified | 2026-05-18 PM, text round-trip ✓ (slack RX → TX both directions) |

**Two gotchas surfaced during this ship (both documented in topic memory):**
1. **xapp- cross-wire silent fail** — Marketing initially had school's xapp- (same 98-char shape, no error log, bot connected to wrong app). Verify post-restart via slack-bolt DEBUG `connection_info.app_id`.
2. **`bot.log` vs `bot-loop.log` log split** — slack-bolt INFO/ERROR goes to `bot-loop.log` (via wrapper `>> "$LOG" 2>&1`), NOT `bot.log`. Tail both when debugging.

**Rollback (per-bot, isolated blast radius):**
```bash
ssh eleva 'cp ~/.school/scripts/school-bot.py.bak-v2-pretslack ~/.school/scripts/school-bot.py && \
  tmux send-keys -t claud-school-bot C-c; sleep 2; \
  tmux send-keys -t claud-school-bot "~/.school/scripts/school-bot-loop.sh" Enter'
```
Restores Telegram-only behavior; Slack channel sits empty without harm.

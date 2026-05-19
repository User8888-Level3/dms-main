# SESSION-STATE — Web-Eleva

> Read first on session resume. Reflects current operational state of the Web Claude Code session on Eleva VPS.

## Last verified

2026-05-17 (build day)

## What's running

| Component | State | How to verify |
|---|---|---|
| Tmux REPL session `claud-web` | Up on Eleva | `ssh eleva 'tmux ls \| grep claud-web'` |
| Tmux bot session `claud-web-bot` | Up on Eleva | same as above |
| Bisync cron | `4-59/5 * * * *` (every 5 min, offset 4) | `ssh eleva 'crontab -l \| grep web-bisync'` |
| Bot process `web-bot.py` | Running under tmux | `ssh eleva 'pgrep -af web-bot.py'` |
| Bot loop wrapper | Running under tmux | `ssh eleva 'pgrep -af web-bot-loop'` |
| Workspace sync state | Last bisync `exit=0` recent | `ssh eleva 'tail -3 ~/.web/logs/bisync.log'` |

## File counts (snapshot at build)

| Surface | Files | Bytes |
|---|---|---|
| Google Drive cloud | 25,854 | 1.14 GiB |
| Mac Drive client (stream) | 25,854 | 1.14 GiB (stream, mostly stubs) |
| Eleva `~/workspaces/Web/` | 25,854 (target — verify after seed) | 1.14 GiB |
| OneDrive backup (retiring) | (pre-migration) | (pre-migration) |

**Note:** The bulk of the file count is `harvrealtor-net/node_modules/` (~16-18k small JS files). Bytes are dominated by `blog/` images and Dec 2024 screenshot PNGs.

## What this Claude session is for

Asset lookup + content drafting for HarvRealtor.com and the broader Web folder:
- Blog posts (drafts, edits, SEO)
- Landing pages
- Market reports (by city, by month)
- FAQ documents
- HarvRealtor.com source (`harvrealtor-net/` React app — content only, not deploys)
- harvinder.dscloud.me archive (Synology-hosted personal site)

## Recent state changes

- **2026-05-17** — Initial ship. 3-way sync (Mac Drive ↔ Drive cloud ↔ Eleva). Voice-enabled Telegram bot `@ElevaWeb_bot`. `claude-web` Mac alias added. Pattern mirrors Marketing + Open House.
- **2026-05-17 evening** — Smoke test PASSED: text in→out, voice in→out (Groq STT + ElevenLabs TTS), allowlist enforced. Workspace-side docs added at `Web/CLAUDE.md` + `Web/_workflow/2026-05-17-eleva-claude-onboarding.md`. OneNote page created at Computers → "Eleva Web Claude" section.
- **2026-05-18 morning** — Seed completed (rclone copy finished after 47 min, killed in cleanup phase). Bot was Ctrl-C'd at 17:32 yesterday; restarted 07:31 today. Bisync `--resync` baseline: exit=0 at 07:32:59. Cron added `4-59/5 * * * *`. Verification bisync exit=0 at 07:41:37. Telegram completion ping delivered to Harv at 07:42. Workspace docs (`Web/CLAUDE.md`, `_workflow/...md`) verified on Eleva. **Full ship complete.** See `SESSION-CONTINUATION-2026-05-18.md` for next-session pickup.

## Pending / open items

- OneDrive `Web/` backup retire target: ~2026-05-26 (9 days post-migration; staggered one day after Marketing).
- Potential filter optimization: `harvrealtor-net/node_modules/**` exclusion could shrink sync from 25.8k → ~5k files. Currently NOT applied per Harv's "no filters" decision. Revisit if bisync API burst becomes a concern.
- Multi-turn Telegram via `claude --resume` keyed by chat_id (deferred across all three sister bots).
- Systemd persistence for the bot (deferred across all three sister bots).

## Eleva snapshot

`94416044` (shared with Marketing + Open House builds, expires 2026-06-05). Take a fresh snapshot if any structural change is made before then.

---

## Slack surface — SHIPPED 2026-05-18 PM

Bot now listens on **BOTH Telegram and Slack** via Socket Mode. Surface-agnostic core handles both. See memory `project-eleva-sisters-slack.md` for full architecture and `School-Broker-Eleva/docs/plans/2026-05-18-eleva-sisters-slack.md` for the implementation plan.

| Field | Value |
|---|---|
| Slack channel | `#eleva-web` |
| Channel ID | `C0B5GJ1PDS4` |
| Bot user ID | `U0B4Q5EK649` |
| Slack app ID | `A0B4FT4NETD` |
| Slack workspace | HarvRealtor.com (`T09GWT09X0C`) |
| Allowlist | `U09GPA82345` (Harv only) |
| Telegram bot | @ElevaWeb_bot (unchanged from v1) |
| Env vars added (mode 600) | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_CHANNEL_ID`, `SLACK_ALLOWED_USERS` |
| Bot code | refactored ~393 → ~531 lines; extracted `handle_message_core` + Slack adapter |
| Backup | `~/.web/scripts/web-bot.py.bak-v2-pretslack` |
| Slack lib | `slack-bolt 1.28.0` via `pip3 install --user --break-system-packages` on Eleva |
| Smoke verified | 2026-05-18 PM, text round-trip ✓ (slack RX → TX both directions) |

**Two gotchas surfaced during this ship (both documented in topic memory):**
1. **xapp- cross-wire silent fail** — Marketing initially had school's xapp- (same 98-char shape, no error log, bot connected to wrong app). Verify post-restart via slack-bolt DEBUG `connection_info.app_id`.
2. **`bot.log` vs `bot-loop.log` log split** — slack-bolt INFO/ERROR goes to `bot-loop.log` (via wrapper `>> "$LOG" 2>&1`), NOT `bot.log`. Tail both when debugging.

**Rollback (per-bot, isolated blast radius):**
```bash
ssh eleva 'cp ~/.web/scripts/web-bot.py.bak-v2-pretslack ~/.web/scripts/web-bot.py && \
  tmux send-keys -t claud-web-bot C-c; sleep 2; \
  tmux send-keys -t claud-web-bot "~/.web/scripts/web-bot-loop.sh" Enter'
```
Restores Telegram-only behavior; Slack channel sits empty without harm.

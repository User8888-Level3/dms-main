# Session Continuation — 2026-05-18 PM (Eleva Sisters Slack ship)

> **For Claude opening fresh.** This is the comprehensive handoff after the Eleva sisters Slack ship session on 2026-05-18 PM. Read top-to-bottom — ~8 min to be fully oriented.
>
> **Status when written:** ✅ ALL planned work shipped + ALL docs/memory/OneNote pushed. No pending action items. 4 sister bots live on BOTH Telegram and Slack. Per-bot identity (4 Slack apps), channel-per-workspace, voice+text on both surfaces, Harv-only allowlist. All 4 smoke-tested with voice round-trip. 7 git commits landed.

## TL;DR — Where things are

| Sister | TG bot | Slack channel | Slack app ID | Bot user ID | Channel ID |
|---|---|---|---|---|---|
| School-Broker | @Eleva_RE_School_bot | `#eleva-school` | `A0B4P11AA65` | `U0B4ETXJZ8T` | `C0B4HQU7XSR` |
| Marketing | @ElevaMarketing_bot | `#eleva-marketing` | `A0B4JBNFVEZ` | `U0B4FCMGR1R` | `C0B4MR6JDUJ` |
| Web | @ElevaWeb_bot | `#eleva-web` | `A0B4FT4NETD` | `U0B4Q5EK649` | `C0B5GJ1PDS4` |
| Open House | (own TG bot) | `#eleva-openhouse` | `A0B4G1FNKSP` | `U0B4Q7545H7` | `C0B5GLY1HL0` |

- **Slack workspace:** HarvRealtor.com (`T09GWT09X0C`)
- **Harv's Slack user ID (allowlist):** `U09GPA82345`
- **All 4 channels:** private (scopes are `groups:*` not `channels:*`)
- **All 4 bots ran voice round-trips on Slack during the session** (logs prove it)

## What got done this session (the big arc)

This morning Harv shipped sister #4 (School-Broker) — all 4 sisters running Telegram bots. Tonight added Slack as a parallel input/output surface for ALL 4 simultaneously.

| Phase | Description | Status |
|---|---|---|
| Brainstorm | One Slack app per bot (vs unified) vs proxy. Chose per-bot apps. | ✅ |
| Design doc | `docs/plans/2026-05-18-eleva-sisters-slack-parallel-surface-design.md` (commit b17a878) | ✅ |
| Implementation plan | 20 tasks in 6 phases (commit e4fd889) | ✅ |
| Pilot manifest | eleva-school.yaml (commit 9f6bdb7) | ✅ |
| Harv: app + install + xapp + channel + bot invite for School | | ✅ |
| Eleva-side prep | slack-bolt installed via --break-system-packages | ✅ |
| Refactor school-bot.py | Extract handle_message_core, threading.Lock around run_claude (commit 8506fd1) | ✅ |
| Add Slack adapter | Socket Mode listener, _scrub, slack_handle_event, dual-listener main (commit 26dc8c8) | ✅ |
| School smoke test | Text + voice both directions, kill-9 recovery (Test 6) | ✅ |
| Sister manifests | 3 more manifests sed-cloned from school (commit 03a58a8) | ✅ |
| Marketing setup | App + tokens + channel + env + code clone | ✅ (after 30-min xapp- cross-wire debug) |
| Web setup | First-shot success | ✅ |
| Open House setup | First-shot success | ✅ |
| Ship-complete pings | 8 total: 4 TG + 4 Slack | ✅ |
| Docs: 4 SESSION-STATE.md updates | Append "Slack surface" section per sister (commit 196cf47) | ✅ |
| Docs: PICKUP-2026-05-19 (now superseded by this file) | | ✅ |
| Memory: new comprehensive topic | `project-eleva-sisters-slack.md` | ✅ |
| Memory: MEMORY.md index updates | 3 new ★ entries (project + 2 feedback rules) | ✅ |
| Memory: append "Slack v2" to 4 sister project files | | ✅ |
| Memory: 2 new feedback rules | scratchpad-secrets audit + verify-app-token-binding | ✅ |
| Drive workspace primers | 4 CLAUDE.md files updated (bisync to Eleva) | ✅ |
| OneNote: 4 new pages | "Slack Surface — 2026-05-18 PM Ship" in each Eleva-* section | ✅ |

## Key gotchas discovered (and the durable rules they spawned)

### G1: xapp- cross-wire silent fail (cost 30 min on Marketing)

The App-Level Token must be generated on the SPECIFIC app's Basic Information page. Easy to copy a prior sister's xapp- from a scratch buffer/KeePassXC by mistake. Symptom: bot connects via Socket Mode (`⚡️ Bolt app is running!`) but to the WRONG app's session — events to the correct channel never reach this bot. **No error logs anywhere.**

**Diagnosis:** enable DEBUG logging temporarily, restart, look at first `on_message` event's `connection_info.app_id`. Must match expected app ID per the canonical table.

**Defense:** at .env paste time, hash-dedup the new xapp- against all prior sisters' xapp- SHA-256 values. See `memory/feedback-verify-app-token-binding.md`.

### G2: bot.log vs bot-loop.log split

Custom `log()` writes to `~/.<x>/logs/bot.log`. The `*-bot-loop.sh` wrapper redirects stdout/stderr to `~/.<x>/logs/bot-loop.log` via `>> "$LOG" 2>&1`. Slack-bolt's INFO logs ("session established", "Bolt app is running!", DEBUG `on_message` traces) go to stderr → bot-loop.log, NOT bot.log. **Tail BOTH when debugging Slack.**

### G3: slack-bolt DEBUG suppressed without basicConfig

Inject temporarily for incident diagnosis (near top of bot.py):
```python
import logging
logging.basicConfig(level=logging.DEBUG, format="[%(asctime)s] slack-bolt: %(name)s %(levelname)s %(message)s")
```
Remove after verification. Default WARNING is preferable in steady state (less log volume).

### G4: Slack search index lag

`slack_search_channels` MCP returns "No results found" for 2-5 minutes after channel creation. Don't trust the negative — ask user to paste channel link and parse the `C0[A-Z0-9]+` segment.

### G5: Chrome MCP can't drive Slack admin (3 walls)

- **OAuth Install/Allow** — security boundary, refuses by design.
- **Slack web client** (app.slack.com) — loads as error in MCP-controlled tab. Use Slack desktop or api.slack.com instead.
- **api.slack.com "Create New App"** — React `isTrusted` event check rejects programmatic clicks.

**Chrome MCP CAN drive:** App-Level Token Generate flow (button works there), api.slack.com forms in general, clipboard-mediated value extraction.

### G6: Files-as-scratchpad contamination (hit TWICE this session!)

Harv pastes tokens/Signing Secrets/secure-terminal commands into whatever YAML or MD file he has open during a credentialing flow. **Caught at session end:** eleva-school.yaml had grown 32→50 lines with 5 secret patterns; eleva-marketing.yaml 32→38 lines with 1 pattern. Both scrubbed before this file was written. See `memory/feedback-audit-files-for-scratchpad-secrets.md`.

**Defense:** grep working tree for secret patterns before ANY `git add`:
```bash
grep -ciE "xox[bap]-[A-Za-z0-9-]{20,}|[Ss]igning [Ss]ecret|[a-f0-9]{32}|xapp-1-" <file>
```
Must return 0. Scrub via line-range truncation (`head -n 32 file > tmp && mv tmp file`), never sed-by-value (echoes secrets).

### G7: PEP 668 on Ubuntu 24.04

`pip3 install --user slack-bolt` fails with "externally-managed-environment". Use `--break-system-packages` flag.

## Live operational state (verified 2026-05-18 ~18:30 PT)

| Field | Value |
|---|---|
| Eleva VPS | `srv1379773` Hostinger Ubuntu 24.04, alias `eleva` |
| Bots alive | 4 (all 4 sister `*-bot.py` processes) |
| Tmux sessions | 4 REPLs + 4 bot supervisors = 8 total |
| Slack ⚡ Bolt sessions | 4 active, one per bot, each bound to correct app (verified via DEBUG `connection_info.app_id`) |
| Telegram surfaces | All 4 bots polling, no 409 conflicts |
| Voice round-trips verified today | school, marketing, web, openhouse — all 4 on Slack with voice in + voice out |
| Bisync crons | offsets 0/1/2/4 mod 5 — no overlap |
| Eleva snapshot | `94416044` (shared with sisters from morning ship, expires 2026-06-05) |
| Slack workspace | HarvRealtor.com ($T09GWT09X0C$) |
| New feedback memory rules added | 2 (audit-files-for-scratchpad-secrets, verify-app-token-binding) |
| Pending macOS Reminders | 2026-05-25 Marketing cleanup, 2026-05-26 Web cleanup, 2026-05-27 School cleanup |

## Where everything lives (5 surfaces)

### 1. Mac repo (OneDrive-Personal/ClaudeCode/)
**Commits this session:**
```
b17a878  docs(eleva-sisters): slack as parallel surface design
e4fd889  docs(eleva-sisters): slack implementation plan (20 tasks, 6 phases)
9f6bdb7  feat(eleva-school-slack): pilot Slack app manifest
8506fd1  feat(eleva-school-slack): extract surface-agnostic core (Telegram still works)
26dc8c8  feat(eleva-school-slack): add Slack adapter + dual-listener main
03a58a8  feat(eleva-sisters-slack): manifests for marketing, web, openhouse
196cf47  docs(eleva-sisters-slack): 4 SESSION-STATE updates + 2026-05-19 pickup
```
**Files added:**
- `School-Broker-Eleva/docs/plans/2026-05-18-eleva-sisters-slack-parallel-surface-design.md`
- `School-Broker-Eleva/docs/plans/2026-05-18-eleva-sisters-slack.md`
- `School-Broker-Eleva/slack-app-manifests/eleva-{school,marketing,web,openhouse}.yaml`
- `School-Broker-Eleva/scripts-snapshot/school-bot.py.phase3-extract` (after refactor)
- `School-Broker-Eleva/scripts-snapshot/school-bot.py.phase3-slack` (after adding Slack)
- `School-Broker-Eleva/PICKUP-2026-05-19-slack-sisters-docs.md` (SUPERSEDED by this file)
- `{School-Broker,Marketing,Web,OpenHouse}-Eleva/SESSION-STATE.md` (each got a Slack section appended)
- THIS FILE: `School-Broker-Eleva/SESSION-CONTINUATION-2026-05-18-pm-slack-sisters.md`

### 2. Memory (`~/.claude/projects/.../memory/`)
**Created:**
- `project-eleva-sisters-slack.md` — CANONICAL comprehensive reference (canonical identity table, architecture, env vars, manifest, setup procedure, 7 gotchas, diagnostic recipes, rollback). **READ FIRST for any future Slack debug.**
- `feedback-audit-files-for-scratchpad-secrets.md`
- `feedback-verify-app-token-binding.md`

**Modified:**
- `MEMORY.md` — added 3 ★ entries (sisters-slack in Active Projects, 2 feedback rules in Secrets & Credentials)
- `project-eleva-school-broker-claude.md` — appended "Slack surface (v2)" section
- `project-eleva-marketing-claude.md` — same
- `project-eleva-web-claude.md` — same
- `project-eleva-openhouse-claude.md` — same

### 3. Drive workspaces (Google Drive, bisynced to Eleva ~/workspaces/)
**Modified (4 files):**
- `~/Library/CloudStorage/GoogleDrive-harvinder.balu@gmail.com/My Drive/School-Broker/CLAUDE.md`
- `~/.../My Drive/Marketing/CLAUDE.md`
- `~/.../My Drive/Web/CLAUDE.md`
- `~/.../My Drive/Open House/CLAUDE.md`

Each got a "Slack surface (v2) — SHIPPED 2026-05-18 PM" section. Bisync cron propagates to Eleva within 5 min.

### 4. Eleva VPS (`srv1379773`)
**Per sister `<x>` in {school, marketing, web, openhouse}:**
- `~/.<x>/.env` — appended 4 SLACK_* env vars (mode 600 preserved)
- `~/.<x>/scripts/<x>-bot.py` — refactored from ~393 → ~531 lines
- `~/.<x>/scripts/<x>-bot.py.bak-v2-pretslack` — pre-refactor backup
- Tmux session `claud-<x>-bot` restarted; logs in `~/.<x>/logs/{bot,bot-loop}.log`
- `slack-bolt 1.28.0` + `slack-sdk 3.42.0` installed globally via `pip3 install --user --break-system-packages`

### 5. OneNote (Computers notebook, 4 new pages)
| Section | New page |
|---|---|
| Eleva School Claude | "Slack Surface — 2026-05-18 PM Ship" |
| Eleva Marketing Claude | "Slack Surface — 2026-05-18 PM Ship" |
| Eleva Web Claude | "Slack Surface — 2026-05-18 PM Ship" |
| Eleva Open House Claude | "Slack Surface — 2026-05-18 PM Ship" |

Each page includes: identifiers table, env vars, architecture, how-to-use, manifest summary, 3 gotchas (G1/G2/G3), rollback command, health check command, references. Created via Graph API POST (NEW page in section) — NOT edit-in-place on the existing Build & Configuration page (to avoid the action=replace clobber risk from morning's School-Broker ship).

## Decision tree — if user says X, do Y

| User says... | You do... |
|---|---|
| "How are the bots?" | `ssh eleva 'pgrep -af "python3 .*-bot.py" \| grep -v pgrep'` (expect 4). Then tail each `~/.{w}/logs/bot.log` for recent slack RX or TX. |
| "Slack bot X stopped responding" | (a) Check process alive. (b) `tail ~/.{X}/logs/bot-loop.log` for `Bolt app is running!`. (c) Enable DEBUG logging if needed, restart, check `connection_info.app_id` matches X's app ID per canonical table. |
| "Add another allowed user to bot X" | Edit `eleva:~/.{X}/.env` `SLACK_ALLOWED_USERS=` line (comma-separated), then `tmux send-keys -t claud-{X}-bot C-c; sleep 2; tmux send-keys -t claud-{X}-bot "~/.{X}/scripts/{X}-bot-loop.sh" Enter`. |
| "Bot is in wrong channel / move to different channel" | Edit `SLACK_CHANNEL_ID=` in `~/.{X}/.env`, invite bot to new channel via `/invite @Eleva {X} Bot`, restart. |
| "Voice on Slack costs are too high" | Check ElevenLabs usage. Lower `TTS_MAX_CHARS = 1500` in `~/.{X}/scripts/{X}-bot.py`. |
| "Roll back Slack on bot X" | `cp ~/.{X}/scripts/{X}-bot.py.bak-v2-pretslack ~/.{X}/scripts/{X}-bot.py && restart`. Telegram-only restored; Slack channel sits empty. |
| "I need a 5th sister bot" | Read `memory/project-eleva-sisters-slack.md` "Setup procedure per sister" — replay-ready 8-step recipe. Also read the implementation plan + new feedback rules. |
| "OneNote MS365 MCP auth failing" | Try `verify-login` first. If fail, RT-refresh via curl using `~/.ms365-mcp/token-cache.json` (worked tonight, see `feedback-check-memory-before-improvising-on-auth.md`). |
| "Need to give a secret to the bot" | Per `feedback-secret-transfer-via-terminal-not-chat.md`: hand Harv a `ssh -t … read -rsp …` block to paste in HIS terminal. Never paste secrets in chat. |
| "I'm about to commit something" | Run secret-scan first: `grep -ciE "xox[bap]-\|signing.?secret\|[a-f0-9]{32}\|xapp-1-" <files>`. Must return 0. (Per `feedback-audit-files-for-scratchpad-secrets.md`.) |

## Things to NOT do (carrying forward)

- ❌ **Don't restart bots unless verifying a fix** — all 4 stable, productive uses ongoing
- ❌ **Don't run `--resync`** on any bisync — all sisters baselined
- ❌ **Don't echo `xoxb-`/`xapp-` values in chat** — use SHA-256 hash if comparing
- ❌ **Don't PATCH OneNote pages with `action=replace`** — clobbers. Use `action=append` against a `data-id` anchor, OR create new page in section (preferred for major additions)
- ❌ **Don't paste secrets directly into manifest YAMLs or MD files** — happened twice this session, scrubbed both times. Use KeePassXC or `/tmp/_scratch.md` (mode 600)
- ❌ **Don't commit anything from `slack-app-manifests/`** without first running the secret scan
- ❌ **Don't try to drive Slack OAuth Install via Chrome MCP** — refuses by design (G5)
- ❌ **Don't trust slack_search_channels "No results found"** in the first 5 min after channel creation (G4)

## Pending / scheduled (auto-fires)

| When | What | Where |
|---|---|---|
| **2026-05-25 10:05 AM PT** | Marketing OneDrive cleanup reminder | macOS Reminder + Hermes cron `marketing-cleanup` |
| **2026-05-26 10:00 AM PT** | Web OneDrive cleanup reminder | macOS Reminder only |
| **2026-05-27 10:00 AM PT** | School-Broker OneDrive cleanup reminder | macOS Reminder only |
| 2026-06-05 | Eleva snapshot `94416044` expires | Hostinger 20-day retention. Take fresh snapshot if structural changes happen. |

## Deferred / next-session candidates (NOT blocking)

- **Systemd units for bots** — still tmux-based. If Eleva reboots, bots don't auto-restart. Mirror OpenClaw's systemd-user-service pattern across all 4 sisters as a separate ship.
- **Per-bot venv** instead of `--break-system-packages` — cleaner if any dep conflicts arise.
- **Multi-turn Slack threads** — `@app.event("message")` with `thread_ts` → key by chat_id+thread_ts → `claude --resume <session-id>` for branching context.
- **TTS cost monitor** — ElevenLabs spend may grow with two surfaces; add daily cost report.
- **Cross-surface conversation continuity** (start TG, continue Slack) — out of scope.
- **Open House TG bot username** — not captured in canonical table (the slot shows "(own TG bot)"). Look up via `grep TELEGRAM_BOT_TOKEN ~/.openhouse/.env` + Telegram getMe API if needed.

## Quick health check on session start

```bash
ssh eleva 'echo "=== Bots (expect 4) ==="; pgrep -af "python3 .*-bot.py" | grep -v pgrep; \
echo ""; for w in school marketing web openhouse; do \
  echo "=== $w ==="; \
  tail -5 ~/.$w/logs/bot.log | grep -E "slack RX|TX surface=slack|START|SLACK: starting|surface=telegram"; \
done; \
echo ""; echo "=== Last bisync per sister ==="; \
for w in school marketing web openhouse; do echo "$w: $(tail -1 ~/.$w/logs/bisync.log 2>/dev/null || echo no-log)"; done; \
echo ""; echo "=== Tmux ==="; tmux ls | head -10'
```

Expected: 4 bot processes, recent slack+TG activity per sister, bisync logs all `exit=0`, 8 tmux sessions.

## Onboarding sequence for fresh Claude session

1. Read THIS file end-to-end.
2. Read `memory/project-eleva-sisters-slack.md` (the canonical topic reference).
3. Quick health check (command above).
4. Use the canonical identity table for IDs — don't grep around for them.
5. Per-bot logs are at `~/.<x>/logs/{bot,bot-loop}.log` (BOTH for full picture).
6. New feedback memory rules govern any future Slack work: `feedback-verify-app-token-binding.md`, `feedback-audit-files-for-scratchpad-secrets.md`.

## Sister cross-refs

- `Web-Eleva/SESSION-CONTINUATION-2026-05-18.md` — Web ship handoff (morning Web finalization)
- `School-Broker-Eleva/SESSION-CONTINUATION-2026-05-18.md` — School ship handoff (morning sister #4)
- `Marketing-Eleva/SESSION-CONTINUATION-2026-05-17.md` — Marketing handoff
- `OpenHouse-Eleva/PICKUP-2026-05-16.md` — Open House ship
- `memory/project-eleva-{marketing,openhouse,web,school-broker}-claude.md` — sister-specific memory files (each got a "Slack surface (v2)" section appended this session)

## Final state at shutdown (2026-05-18 ~18:30 PT)

✅ 4 Slack apps created + installed + manifests committed
✅ 4 channels + bot invites in HarvRealtor.com workspace
✅ 4 `.env` files (4 SLACK_ vars each, hash-deduped against cross-wire)
✅ 4 bot.py refactors (393 → ~531 lines, surface-agnostic core + Slack adapter)
✅ 8 ship-complete pings (4 TG + 4 Slack)
✅ 7 git commits on main (b17a878 → 196cf47)
✅ 1 new comprehensive memory topic file + 2 new feedback rules + 3 ★ index updates + 4 sister project file appendices
✅ 4 Drive workspace CLAUDE.md primers updated (bisync to Eleva)
✅ 4 OneNote pages created in Computers notebook
✅ 2 manifest YAML scratchpad contamination incidents caught and scrubbed (committed versions always clean)
✅ MS365 OneNote auth restored via curl-based RT refresh (silent acquisition still broken — known issue, RT refresh workaround proven)

**No outstanding action items. No pending failures. Bots productive and being used.**

---

*Written by Mac Claude (Opus 4.7) at 2026-05-18 ~18:35 PT, end of Eleva sisters Slack ship session. Harv is about to clear the context window. Next-me: read top-to-bottom, then proceed with whatever Harv asks. The 4 sisters are stable and require no intervention. The 2 new feedback rules cover the failure modes most likely to recur.*

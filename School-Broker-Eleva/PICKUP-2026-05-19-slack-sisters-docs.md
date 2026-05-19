# Eleva Sisters Slack — Pickup for Docs/Memory (2026-05-19 morning)

> **Status when written:** All 4 sister bots live on BOTH Telegram + Slack as of 2026-05-18 ~18:13 PT. Ship-complete pings delivered on all 8 surfaces (4 TG + 4 Slack). What remains is housekeeping only — Harv is not in the loop for any of it.

## What's live

| Sister | Channel | Channel ID | Bot User ID | xapp hash prefix |
|---|---|---|---|---|
| School-Broker | `#eleva-school` | `C0B4HQU7XSR` | `U0B4ETXJZ8T` | `06adb64a` |
| Marketing | `#eleva-marketing` | `C0B4MR6JDUJ` | `U0B4FCMGR1R` | `0b3bf13a` |
| Web | `#eleva-web` | `C0B5GJ1PDS4` | `U0B4Q5EK649` | `275c18a5` |
| Open House | `#eleva-openhouse` | `C0B5GLY1HL0` | `U0B4Q7545H7` | `67249333` |

Harv's Slack user ID: `U09GPA82345`. Workspace: `T09GWT09X0C` (HarvRealtor.com).

## What remains (do tomorrow morning)

### Task 17: Update SESSION-STATE.md for each Eleva-sister workspace
- `School-Broker-Eleva/SESSION-STATE.md` — add "Slack surface SHIPPED 2026-05-18-pm" section
- `Marketing-Eleva/SESSION-STATE.md` — same
- `Web-Eleva/SESSION-STATE.md` — same
- `OpenHouse-Eleva/SESSION-STATE.md` — same

Each entry: channel name + ID (last 4 chars only for safety), bot user ID, env-var keys appended, deps installed (`slack-bolt 1.28.0`, `slack-sdk 3.42.0` via `pip3 install --user --break-system-packages` on Ubuntu 24.04).

### Task 18: Memory updates
**Already saved tonight (commit pending):**
- `memory/feedback-audit-files-for-scratchpad-secrets.md` — Harv scratchpads tokens into open YAML files; pre-commit secret-scan as defense
- `memory/feedback-verify-app-token-binding.md` — xapp- can cross-wire between sister apps; verify via apps.connections.open

**Tomorrow:** add ★ entry to `MEMORY.md` "Active Projects" section pointing to a new project topic file:
- Create `memory/project-eleva-sisters-slack.md` summarizing the architecture (2-thread bot, surface-agnostic core + adapters, manifest pattern, app/channel/token table, key gotchas).
- Cross-link the 4 existing sister project files (`project-eleva-marketing-claude.md`, etc.) by adding a "Slack surface (v2) — SHIPPED 2026-05-18" section to each.

### Task 19: OneNote
Append a "Slack surface — 2026-05-18" block to each of the 4 OneNote app/workspace pages (Computers notebook → "Eleva [X] Claude" section). **Use Graph API PATCH with `action=append` against an anchor**, NOT `action=replace` — clobbers the page (gotcha from morning's session).

## Key learnings to bake into the topic memory file

1. **xapp- cross-wire bug** (Marketing). Manifest pasting created the app, install generated xoxb-, but generating xapp- requires being on THAT app's Basic Information page. Harv re-copied school's xapp- thinking he was generating Marketing's. Symptom: bot connects via Socket Mode but to wrong app's session (connection_info.app_id mismatches expected). 30 min lost diagnosing. Fix: hash-dedup xapp- tokens at .env paste time; verify connection_info.app_id post-restart.

2. **bot.log vs bot-loop.log split.** Custom `log()` writes to `bot.log`. Python stdout/stderr (including slack-bolt internal logs) → `bot-loop.log` via the wrapper's `>> "$LOG" 2>&1`. Tail BOTH when debugging — slack-bolt's `⚡️ Bolt app is running!` confirmation only appears in bot-loop.log.

3. **slack-bolt INFO is suppressed without basicConfig.** Without `logging.basicConfig(level=logging.INFO, ...)` at the top of bot.py, slack-bolt's INFO-level logs (including "session established", connection_info debug data) are at DEBUG/INFO and don't surface. For incident diagnosis: temporarily inject `logging.basicConfig(level=logging.DEBUG, ...)`, restart, observe `on_message invoked` lines with raw event payloads.

4. **Slack search index lag.** `slack_search_channels` can take 2-5 min after channel creation. Don't trust "No results found" as evidence the channel doesn't exist. Workaround: ask user to paste channel link, parse the `C0...` ID.

5. **Chrome MCP can't drive Slack admin flows** (3 hard walls hit in one session):
   - OAuth Install + Allow (security boundary by design)
   - Slack web app client (loads as error in MCP tab — known issue)
   - api.slack.com "Create New App" button (React `isTrusted` event check)
   It CAN drive App-Level Token generation (button works there) and clipboard-mediated value transfer.

6. **Files-as-scratchpad pattern.** Harv pastes tokens/secrets into adjacent YAML/markdown files when mid-flow. Always grep for `xox[bap]-|signing.?secret|[a-f0-9]{32}|xapp-1-` before `git add`. Pre-commit secret-scan saved one commit tonight (manifest YAML had Signing Secret + xoxb + xapp + ssh command before scrub).

## Quick health check on session start

```bash
ssh eleva 'echo "=== bots alive (expect 4) ==="; pgrep -af "python3 .*-bot.py" | grep -v pgrep; \
echo "=== slack RX in last hour (any sister) ==="; \
for w in school marketing web openhouse; do echo "--- $w ---"; tail -5 ~/.$w/logs/bot.log | grep -E "slack RX|TX surface=slack" || echo "(no recent slack activity)"; done; \
echo "=== last bisync per sister ==="; \
for w in school marketing web openhouse; do echo "--- $w ---"; tail -1 ~/.$w/logs/bisync.log 2>/dev/null || echo "(no bisync log)"; done'
```

Expected: 4 bot processes, slack activity in at least school (from earlier smoke), bisync logs recent for all 4.

## What NOT to touch

- ❌ Don't restart any bot unless verifying a fix — they're all stable
- ❌ Don't run `--resync` on bisync — all 4 sisters are baselined
- ❌ Don't echo any xoxb-/xapp- value in chat — use SHA-256 hash if comparing
- ❌ Don't PATCH OneNote pages with `action=replace` — clobbers. Use `action=append`.

## Files touched in this session (Mac repo)

```
School-Broker-Eleva/docs/plans/2026-05-18-eleva-sisters-slack-parallel-surface-design.md  (commit b17a878)
School-Broker-Eleva/docs/plans/2026-05-18-eleva-sisters-slack.md                          (commit e4fd889)
School-Broker-Eleva/slack-app-manifests/eleva-school.yaml                                 (commit 9f6bdb7, scrubbed)
School-Broker-Eleva/slack-app-manifests/eleva-marketing.yaml                              (commit 03a58a8)
School-Broker-Eleva/slack-app-manifests/eleva-web.yaml                                    (commit 03a58a8)
School-Broker-Eleva/slack-app-manifests/eleva-openhouse.yaml                              (commit 03a58a8)
School-Broker-Eleva/scripts-snapshot/school-bot.py.phase3-extract                         (commit 8506fd1)
School-Broker-Eleva/scripts-snapshot/school-bot.py.phase3-slack                           (commit 26dc8c8)
memory/feedback-audit-files-for-scratchpad-secrets.md                                     (not yet committed)
memory/feedback-verify-app-token-binding.md                                               (not yet committed)
```

## Files touched on Eleva

```
~/.{school,marketing,web,openhouse}/.env                  — 4 new SLACK_* vars per
~/.{school,marketing,web,openhouse}/scripts/*-bot.py      — refactored + Slack adapter (~530 lines from ~393)
~/.{school,marketing,web,openhouse}/scripts/*-bot.py.bak-v2-pretslack  — backup (pre-refactor)
```

`slack-bolt 1.28.0` + `slack-sdk 3.42.0` installed via `pip3 install --user --break-system-packages` on Eleva (Ubuntu 24.04 PEP 668).

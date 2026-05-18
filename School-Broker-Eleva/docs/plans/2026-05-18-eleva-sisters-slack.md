# Eleva Sisters — Slack as Parallel Surface — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Slack as a second concurrent input/output surface (alongside Telegram) for all 4 sister bots on Eleva — voice + text on both surfaces, one Slack app per workspace, channel-per-workspace allowlist model.

**Architecture:** Each `*-bot.py` becomes a 2-thread Python process: existing Telegram long-poll loop + new `slack-bolt` SocketModeHandler. Both threads converge on a surface-agnostic `handle_message_core()`. A `threading.Lock` around `run_claude()` serializes concurrent invocations.

**Tech Stack:** Python 3.x, `slack-bolt` (new dep), existing Groq Whisper + ElevenLabs + `claude -p` infrastructure, Slack Socket Mode (no public webhook), tmux supervisor + `*-bot-loop.sh` (unchanged).

**Pilot strategy:** School-Broker (smallest, freshest) ships first. Validate ≥24h. Then clone the refactor to Marketing, Web, Open House.

**Reference design:** `School-Broker-Eleva/docs/plans/2026-05-18-eleva-sisters-slack-parallel-surface-design.md` (commit `b17a878`)

---

## Phase 0 — Slack app manifest (pilot)

### Task 1: Author Slack app manifest for School-Broker

**Files:**
- Create: `School-Broker-Eleva/slack-app-manifests/eleva-school.yaml`

**Step 1: Write the manifest YAML**

```yaml
display_information:
  name: Eleva RE School Bot
  description: 24/7 Claude on Eleva, scoped to School-Broker workspace
  background_color: "#1a1a1a"

features:
  bot_user:
    display_name: Eleva RE School Bot
    always_online: true

oauth_config:
  scopes:
    bot:
      - chat:write
      - files:write
      - files:read
      - groups:history
      - groups:read
      - im:history
      - im:read
      - users:read

settings:
  event_subscriptions:
    bot_events:
      - message.groups
      - message.im
  interactivity:
    is_enabled: false
  socket_mode_enabled: true
  org_deploy_enabled: false
  token_rotation_enabled: false
```

**Step 2: Commit**

```bash
git add School-Broker-Eleva/slack-app-manifests/eleva-school.yaml
git commit -m "feat(eleva-school-slack): pilot Slack app manifest"
```

---

## Phase 1 — Slack-side setup (gated on Harv)

### Task 2: Harv creates Slack app from manifest

**Out-of-band — Harv does these in his browser:**

1. Go to api.slack.com/apps → "Create New App" → "From a manifest"
2. Pick the right Slack workspace (Harv's premium one)
3. Paste contents of `School-Broker-Eleva/slack-app-manifests/eleva-school.yaml`
4. Review, click "Create"
5. **Basic Information page:** scroll to "App-Level Tokens" → "Generate Token and Scopes" → name `socket-mode` → add scope `connections:write` → "Generate" → **copy the `xapp-...` token**
6. **Install App page:** click "Install to Workspace" → approve → **copy the `xoxb-...` Bot User OAuth Token**

**Step 1: Wait for Harv to confirm both tokens are in his clipboard / password manager.**

No code step. No commit yet.

### Task 3: Harv creates `#eleva-school` private channel

**Out-of-band:**

1. In Slack: `+` next to "Channels" → "Create channel"
2. Name: `eleva-school` · **Private** · Description: "Eleva School-Broker Claude bot"
3. After creation: channel header → `+ Add people` → search "Eleva RE School Bot" → add
4. Channel header → "More" → "Copy link" → channel ID is the `C0xxxxxxxxxx` chunk at the end of the URL

**Step 1: Wait for Harv to confirm channel ID is captured.**

No code step. No commit yet.

---

## Phase 2 — Eleva-side prep

### Task 4: Install slack-bolt on Eleva

**Step 1: Run install**

```bash
ssh eleva 'pip3 install --user slack-bolt'
```

**Expected:** "Successfully installed slack-bolt-X.X.X slack-sdk-X.X.X" (or "Requirement already satisfied")

**Step 2: Verify import works**

```bash
ssh eleva 'python3 -c "from slack_bolt import App; from slack_bolt.adapter.socket_mode import SocketModeHandler; print(\"ok\")"'
```

**Expected:** `ok`

**No commit — this is a remote install only.**

### Task 5: Paste Slack env vars into `~/.school/.env`

**Step 1: Prepare secure terminal-paste block for Harv**

Hand Harv this exact command to run in HIS terminal (do not echo values, do not paste in chat):

```bash
ssh -t eleva 'read -rsp "SLACK_BOT_TOKEN (xoxb-...): " BOT && echo && \
  read -rsp "SLACK_APP_TOKEN (xapp-...): " APP && echo && \
  read -rp "SLACK_CHANNEL_ID (C...): " CHAN && \
  read -rp "SLACK_ALLOWED_USERS (U... — your Slack user ID): " USER && \
  printf "SLACK_BOT_TOKEN=%s\nSLACK_APP_TOKEN=%s\nSLACK_CHANNEL_ID=%s\nSLACK_ALLOWED_USERS=%s\n" "$BOT" "$APP" "$CHAN" "$USER" >> ~/.school/.env && \
  echo "appended 4 lines to ~/.school/.env"'
```

**Step 2: Verify presence without echoing values**

```bash
ssh eleva 'grep -c "^SLACK_" ~/.school/.env'
```

**Expected:** `4`

```bash
ssh eleva 'awk -F= "/^SLACK_/{ printf \"%s=<%d chars>\n\", \$1, length(\$2) }" ~/.school/.env'
```

**Expected:** four lines like `SLACK_BOT_TOKEN=<56 chars>` — confirms presence + non-zero length without leaking value.

**Step 3: Confirm `.env` permissions still 600**

```bash
ssh eleva 'stat -c "%a %n" ~/.school/.env'
```

**Expected:** `600 /home/harvey/.school/.env`

**No commit — these are server-side secrets only.**

---

## Phase 3 — Refactor `school-bot.py` (the pilot)

### Task 6: Backup current `school-bot.py`

**Step 1: Backup**

```bash
ssh eleva 'cp ~/.school/scripts/school-bot.py ~/.school/scripts/school-bot.py.bak-v2-pretslack && ls -la ~/.school/scripts/school-bot.py*'
```

**Expected:** Original + new `.bak-v2-pretslack` file, identical sizes.

**No commit — server-side backup only.**

### Task 7: Pull current `school-bot.py` to Mac for editing

**Step 1: Pull**

```bash
mkdir -p /tmp/eleva-slack-refactor && \
  scp eleva:~/.school/scripts/school-bot.py /tmp/eleva-slack-refactor/school-bot.py
```

**Step 2: Confirm line count matches expected ~393**

```bash
wc -l /tmp/eleva-slack-refactor/school-bot.py
```

**Expected:** ~393 lines.

**No commit — staging only.**

### Task 8: Refactor — extract `handle_message_core()` (Telegram-still-works gate)

**Files:**
- Modify: `/tmp/eleva-slack-refactor/school-bot.py`

**Step 1: Extract surface-agnostic core**

In `school-bot.py`, the current `handle_message(env, token, update)` has Telegram-shaped inputs (token + update dict) and Telegram-shaped outputs (calls `send_message(token, chat_id, ...)`). Refactor so:

- New function `handle_message_core(env, surface, user_id, text, audio_path, reply_text_fn, reply_voice_fn) -> None` contains all the logic from the current `handle_message` AFTER the Telegram-specific extraction (allowlist check, /start /help /status, Whisper transcribe, run_claude, voice/text reply).
- The current `handle_message` becomes a thin Telegram adapter: extract `chat_id`, `user_id`, `text`, optional voice file (download to temp path via `tg_download_file`), build closures `reply_text_fn = lambda t: send_message(token, chat_id, t)` and `reply_voice_fn = lambda mp3_bytes: <tg voice send via mp3_to_ogg + send_voice>`, then call `handle_message_core(env, "telegram", user_id, text, audio_path, reply_text_fn, reply_voice_fn)`.
- The allowlist check inside the core now reads `env[f"{surface.upper()}_ALLOWED_USERS"]` so it works for both `"telegram"` and `"slack"`.
- The voice-out path inside the core now calls `reply_voice_fn(mp3_bytes)` instead of doing Telegram-specific OGG conversion + send_voice. The Telegram adapter's `reply_voice_fn` does the OGG conversion itself.

**Step 2: Wrap `run_claude()` in a module-level `threading.Lock`**

At the top of the file (after imports):

```python
import threading
_claude_lock = threading.Lock()

def run_claude(claude_bin, workdir, prompt):
    with _claude_lock:
        # ... existing body
```

**Step 3: Smoke-test the refactor LOCALLY by reading the diff**

```bash
diff -u <(scp eleva:~/.school/scripts/school-bot.py.bak-v2-pretslack /dev/stdout 2>/dev/null) /tmp/eleva-slack-refactor/school-bot.py | head -100
```

Confirm the diff is structural (function shapes), not behavioral.

**Step 4: Push back to Eleva and restart**

```bash
scp /tmp/eleva-slack-refactor/school-bot.py eleva:~/.school/scripts/school-bot.py
ssh eleva 'tmux send-keys -t claud-school-bot C-c; sleep 2; tmux send-keys -t claud-school-bot "~/.school/scripts/school-bot-loop.sh" Enter'
```

**Step 5: Watch log for clean START**

```bash
ssh eleva 'sleep 3 && tail -20 ~/.school/logs/bot.log'
```

**Expected:** `START — last_update_id=<n>` line, no Python tracebacks.

**Step 6: Smoke-test Telegram regression**

Harv sends a text message to `@Eleva_RE_School_bot` on Telegram. Expected: text reply within 30s, identical UX to pre-refactor.

**Step 7: Commit the refactor (Mac-side, the design plan workspace)**

```bash
cp /tmp/eleva-slack-refactor/school-bot.py "/Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/School-Broker-Eleva/scripts-snapshot/school-bot.py.phase3-extract"
# Note: scripts-snapshot/ is a new dir for capturing the canonical script versions
mkdir -p "/Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/School-Broker-Eleva/scripts-snapshot"
cp /tmp/eleva-slack-refactor/school-bot.py "/Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/School-Broker-Eleva/scripts-snapshot/school-bot.py.phase3-extract"
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode
git add School-Broker-Eleva/scripts-snapshot/school-bot.py.phase3-extract
git commit -m "feat(eleva-school-slack): extract surface-agnostic core (Telegram still works)"
```

### Task 9: Add Slack adapter — listener + I/O wrappers

**Files:**
- Modify: `/tmp/eleva-slack-refactor/school-bot.py`

**Step 1: Add slack-bolt imports at top**

```python
from slack_bolt import App as SlackApp
from slack_bolt.adapter.socket_mode import SocketModeHandler
```

**Step 2: Add Slack I/O helpers**

After the existing Telegram helpers (around the `send_voice` location), add:

```python
# ----- Slack adapter -----

def slack_send_text(client, channel, text):
    try:
        client.chat_postMessage(channel=channel, text=text)
    except Exception as e:
        log(f"slack_send_text error: {type(e).__name__}: {_scrub(e)}")

def slack_send_voice(client, channel, mp3_path):
    try:
        client.files_upload_v2(channel=channel, file=mp3_path, title="Voice reply",
                               filename="reply.mp3", initial_comment="🔊")
    except Exception as e:
        log(f"slack_send_voice error: {type(e).__name__}: {_scrub(e)}")

def slack_download_audio(client, file_obj, dest_path):
    url = file_obj["url_private_download"]
    token = client.token
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r, open(dest_path, "wb") as f:
            f.write(r.read())
        return dest_path
    except Exception as e:
        log(f"slack_download_audio error: {type(e).__name__}: {_scrub(e)}")
        return None

def _scrub(exc):
    # Strip xoxb-/xapp- tokens from exception text before logging
    import re
    s = str(exc)
    s = re.sub(r"xox[bap]-[A-Za-z0-9-]+", "<redacted>", s)
    return s[:300]
```

**Step 3: Add Slack event handler**

```python
def slack_handle_event(env, client, event):
    if event.get("bot_id"):
        return  # ignore our own messages
    chan = event.get("channel", "")
    user = event.get("user", "")
    if chan != env.get("SLACK_CHANNEL_ID", "").strip():
        log(f"slack DROP channel={chan} (not allowlisted)")
        return
    allowed = {u.strip() for u in env.get("SLACK_ALLOWED_USERS", "").split(",") if u.strip()}
    if user not in allowed:
        log(f"slack DENY user={user} (not in allowlist)")
        return

    text = (event.get("text") or "").strip()
    audio_path = None
    files = event.get("files") or []
    for f in files:
        if (f.get("mimetype") or "").startswith("audio/"):
            audio_path = slack_download_audio(client, f, f"/tmp/slack-voice-{uuid.uuid4().hex}.m4a")
            break

    reply_text_fn = lambda t: slack_send_text(client, chan, t)
    def reply_voice_fn(mp3_path):
        slack_send_voice(client, chan, mp3_path)

    log(f"slack RX channel={chan} user={user} text={text[:80]!r} voice={'y' if audio_path else 'n'}")
    handle_message_core(env, "slack", user, text, audio_path, reply_text_fn, reply_voice_fn)
```

**Step 4: Add slack_listen()**

```python
def slack_listen(env):
    bot_token = env.get("SLACK_BOT_TOKEN", "").strip()
    app_token = env.get("SLACK_APP_TOKEN", "").strip()
    if not (bot_token and app_token):
        log("SLACK: not configured (SLACK_BOT_TOKEN or SLACK_APP_TOKEN missing) — skipping Slack listener")
        return
    app = SlackApp(token=bot_token)

    @app.event("message")
    def _on_message(event, client):
        try:
            slack_handle_event(env, client, event)
        except Exception as e:
            log(f"slack_handle_event error: {type(e).__name__}: {_scrub(e)}")

    log("SLACK: starting SocketModeHandler")
    SocketModeHandler(app, app_token).start()
```

**Step 5: Update `main()` to spawn both listeners**

Replace the existing `while True` loop in `main()` with:

```python
def main():
    env = read_env()
    state = load_state()
    log(f"START — last_update_id={state['last_update_id']}")

    # Slack thread
    t_slack = threading.Thread(target=slack_listen, args=(env,), daemon=True, name="slack")
    t_slack.start()

    # Telegram (existing loop) on main thread
    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        log("FATAL: TELEGRAM_BOT_TOKEN not set in ~/.school/.env")
        sys.exit(2)

    while True:
        try:
            r = tg_api(token, "getUpdates",
                       offset=state["last_update_id"] + 1,
                       timeout=LONG_POLL_TIMEOUT,
                       allowed_updates=json.dumps(["message", "edited_message"]))
            # ... rest of existing Telegram loop body unchanged
```

**Step 6: Sanity-check syntax**

```bash
python3 -c "import ast; ast.parse(open('/tmp/eleva-slack-refactor/school-bot.py').read()); print('parse ok')"
```

**Expected:** `parse ok`

**Step 7: Push to Eleva**

```bash
scp /tmp/eleva-slack-refactor/school-bot.py eleva:~/.school/scripts/school-bot.py
```

**Step 8: Restart bot**

```bash
ssh eleva 'tmux send-keys -t claud-school-bot C-c; sleep 2; tmux send-keys -t claud-school-bot "~/.school/scripts/school-bot-loop.sh" Enter; sleep 5; tail -30 ~/.school/logs/bot.log'
```

**Expected:** Both `START` and `SLACK: starting SocketModeHandler` lines, no tracebacks.

**Step 9: Commit (Mac-side snapshot)**

```bash
cp /tmp/eleva-slack-refactor/school-bot.py "/Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/School-Broker-Eleva/scripts-snapshot/school-bot.py.phase3-slack"
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode
git add School-Broker-Eleva/scripts-snapshot/school-bot.py.phase3-slack
git commit -m "feat(eleva-school-slack): add Slack adapter + dual-listener main"
```

### Task 10: Full 6-test smoke (pilot validation)

**Tests run by Harv interactively + observed by Claude via logs:**

| # | Test | Expected |
|---|---|---|
| 1 | Text in `#eleva-school` | Text reply ≤30s in same channel |
| 2 | Voice note in `#eleva-school` | Voice reply (waveform inline) + text alongside |
| 3 | DM the bot directly | Silent drop; log line `slack DROP channel=...` |
| 4 | Text on TG + Slack simultaneously | Both reply; lock serializes; observe ordering in log |
| 5 | `ssh eleva 'pkill -9 -f school-bot.py'` | `*-bot-loop.sh` respawns ≤5s; both surfaces back |
| 6 | Telegram text-only message | Identical to pre-Slack behavior |

**Step 1: Run each test, capture log evidence**

```bash
ssh eleva 'tail -100 ~/.school/logs/bot.log'
```

**Step 2: If all 6 pass → proceed to Phase 4 (24h watch). If any fail → diagnose, fix, re-test before commit.**

**No new commit — validation gate only.**

---

## Phase 4 — Pilot validation gate (24h watch)

### Task 11: Watch School-Broker bot for ≥24h

**Step 1: Set a reminder**

```bash
osascript -e 'tell application "Reminders" to make new reminder with properties {name:"Eleva Slack pilot — School-Broker 24h watch complete; proceed to clone if green", remind me date:(current date) + (24 * 60 * 60)}'
```

**Step 2: When the reminder fires, check bot health**

```bash
ssh eleva 'echo "=== Tmux ==="; tmux ls | grep claud-school; \
echo "=== Process ==="; pgrep -af school-bot.py; \
echo "=== Last 50 log lines ==="; tail -50 ~/.school/logs/bot.log; \
echo "=== Error count ==="; grep -c "error\|FATAL\|traceback" ~/.school/logs/bot.log || echo 0'
```

**Expected:** 1 tmux session, 1 python process, no errors/tracebacks in tail, error count plausibly 0.

**Step 3: GATE — only proceed to Phase 5 if green. If yellow/red, root-cause first.**

---

## Phase 5 — Clone to 3 sisters (gated on pilot green)

### Task 12: Author 3 more Slack app manifests

**Files:**
- Create: `School-Broker-Eleva/slack-app-manifests/eleva-marketing.yaml`
- Create: `School-Broker-Eleva/slack-app-manifests/eleva-web.yaml`
- Create: `School-Broker-Eleva/slack-app-manifests/eleva-openhouse.yaml`

**Step 1: Author each manifest as sed-clone of `eleva-school.yaml`**

For each (`marketing`, `web`, `openhouse`):

```bash
sed -e 's/RE School/Marketing/g; s/School-Broker/Marketing/g' \
    School-Broker-Eleva/slack-app-manifests/eleva-school.yaml \
    > School-Broker-Eleva/slack-app-manifests/eleva-marketing.yaml
# Repeat for web (s/RE School/Web/g; s/School-Broker/Web/g) and openhouse (s/RE School/Open House/g; s/School-Broker/Open House/g)
```

**Step 2: Audit each for stray `school` references**

```bash
grep -i "school" School-Broker-Eleva/slack-app-manifests/eleva-marketing.yaml
grep -i "school" School-Broker-Eleva/slack-app-manifests/eleva-web.yaml
grep -i "school" School-Broker-Eleva/slack-app-manifests/eleva-openhouse.yaml
```

**Expected:** no output (or only intentional refs).

**Step 3: Commit**

```bash
git add School-Broker-Eleva/slack-app-manifests/
git commit -m "feat(eleva-sisters-slack): manifests for marketing, web, openhouse"
```

### Task 13: Harv creates 3 more Slack apps + channels

**Out-of-band, same pattern as Tasks 2 + 3 ×3:**

For each of `marketing`, `web`, `openhouse`:

1. api.slack.com/apps → "From manifest" → paste matching YAML → Create.
2. App-Level Token (`xapp-...`, scope `connections:write`) + Bot User OAuth (`xoxb-...`) → capture both.
3. Create `#eleva-<name>` private channel → invite the bot → capture channel ID.

**Step 1: Confirm 6 tokens + 3 channel IDs captured by Harv.**

No code step. No commit yet.

### Task 14: Paste env vars into 3 sister `.env` files

**Step 1: Hand Harv the secure terminal block (×3, one per workspace)**

Same pattern as Task 5, with `~/.marketing/.env`, `~/.web/.env`, `~/.openhouse/.env` substituted.

**Step 2: Verify presence in each**

```bash
for w in marketing web openhouse; do
  echo "=== $w ==="
  ssh eleva "grep -c '^SLACK_' ~/.$w/.env"
done
```

**Expected:** each prints `4`.

**No commit — server-side secrets only.**

### Task 15: Clone refactored `school-bot.py` to 3 sister bots

**Files:**
- Modify: `~/.marketing/scripts/marketing-bot.py` (on Eleva)
- Modify: `~/.web/scripts/web-bot.py` (on Eleva)
- Modify: `~/.openhouse/scripts/openhouse-bot.py` (on Eleva)

**Step 1: Backup each**

```bash
ssh eleva 'for w in marketing web openhouse; do
  cp ~/.$w/scripts/$w-bot.py ~/.$w/scripts/$w-bot.py.bak-v2-pretslack
done; ls ~/.*/scripts/*pretslack'
```

**Expected:** 3 `.bak-v2-pretslack` files.

**Step 2: Clone School-Broker's bot via sed (per workspace)**

For each workspace name `<w>` in `marketing`, `web`, `openhouse`:

```bash
ssh eleva 'sed -e "s/school/<w>/g; s/School-Broker/<Workspace>/g; s/SCHOOL_WORKDIR/<W>_WORKDIR/g; s/SCHOOL/<W>/g" \
  ~/.school/scripts/school-bot.py \
  > ~/.<w>/scripts/<w>-bot.py.new'
```

Where `<W>` is uppercase, `<Workspace>` is human form (e.g., Marketing, Web, Open-House).

**Step 3: Audit for stray `school` references**

```bash
ssh eleva 'for w in marketing web openhouse; do
  echo "=== $w stray school refs ==="
  grep -n "school\|School" ~/.$w/scripts/$w-bot.py.new || echo "(clean)"
done'
```

**Expected:** `(clean)` for all three. If any stray refs, fix with targeted sed (this was the gotcha from the original ship — line 308 had a missed reference).

**Step 4: Move `.new` into place + restart**

```bash
ssh eleva 'for w in marketing web openhouse; do
  mv ~/.$w/scripts/$w-bot.py.new ~/.$w/scripts/$w-bot.py
  chmod +x ~/.$w/scripts/$w-bot.py
  tmux send-keys -t claud-$w-bot C-c
  sleep 2
  tmux send-keys -t claud-$w-bot "~/.$w/scripts/$w-bot-loop.sh" Enter
  sleep 5
  echo "=== $w log tail ==="
  tail -20 ~/.$w/logs/bot.log
done'
```

**Expected:** Each shows fresh `START` + `SLACK: starting SocketModeHandler` lines.

**Step 5: Mac-side snapshot commit**

```bash
mkdir -p "/Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/School-Broker-Eleva/scripts-snapshot/sister-clones"
for w in marketing web openhouse; do
  scp eleva:~/.$w/scripts/$w-bot.py "/Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/School-Broker-Eleva/scripts-snapshot/sister-clones/$w-bot.py"
done
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode
git add School-Broker-Eleva/scripts-snapshot/sister-clones/
git commit -m "feat(eleva-sisters-slack): clone Slack adapter to marketing, web, openhouse"
```

### Task 16: 6-test smoke per sister bot

**Step 1: For each of `marketing`, `web`, `openhouse`, run the same 6 tests from Task 10 in their respective Slack channel.**

Capture log evidence per workspace:

```bash
ssh eleva 'for w in marketing web openhouse; do
  echo "=== $w ==="; tail -30 ~/.$w/logs/bot.log
done'
```

**Step 2: GATE — only proceed to Phase 6 if all 3 sisters pass all 6 tests.**

---

## Phase 6 — Docs, memory, ship

### Task 17: Update SESSION-STATE.md for each sister workspace

**Files:**
- Modify: `School-Broker-Eleva/SESSION-STATE.md`
- Modify: `Marketing-Eleva/SESSION-STATE.md`
- Modify: `Web-Eleva/SESSION-STATE.md`
- Modify: `OpenHouse-Eleva/SESSION-STATE.md`

**Step 1: Add a new section in each: "Slack parallel surface — SHIPPED 2026-MM-DD" with bot name, channel ID (last 4 chars only for safety), env-var names added, deps installed.**

**Step 2: Commit**

```bash
git add */SESSION-STATE.md
git commit -m "docs(eleva-sisters-slack): record Slack surface ship in SESSION-STATE files"
```

### Task 18: Update memory topic files + MEMORY.md ★ index

**Files:**
- Modify: `memory/project-eleva-school-broker-claude.md`
- Modify: `memory/project-eleva-marketing-claude.md`
- Modify: `memory/project-eleva-web-claude.md`
- Modify: `memory/project-eleva-openhouse-claude.md`
- Modify: `memory/MEMORY.md`

**Step 1: In each topic file, add a "Slack surface (v2)" section noting the channel name, bot name, scopes, and that the bot now runs 2 threads.**

**Step 2: In MEMORY.md, update the ★ entries for all 4 sisters to mention Slack is wired in.**

**Step 3: Add a new topic memory if a durable lesson emerges from the smoke tests (e.g., a new gotcha worth carrying forward).**

**No commit — memory files live outside the git repo per their own layout.**

### Task 19: Update OneNote "Eleva [Workspace] Claude" pages

**Step 1: For each of the 4 workspaces' OneNote pages (Computers notebook → "Eleva [Name] Claude" section), append a "Slack surface — 2026-MM-DD" block via Graph API PATCH with `action=append` (NOT `action=replace` — that clobbered the page last time per the original ship's gotcha #4).**

**Step 2: Verify by reading each page back via `mcp__ms365__get-onenote-page-content`.**

**No commit — OneNote is external.**

### Task 20: Ship-complete Telegram + Slack ping

**Step 1: Send a ship-complete message to Harv from all 4 bots on both surfaces:**

```python
# Via Eleva, simple curl per bot per surface
ssh eleva 'for w in school marketing web openhouse; do
  source ~/.$w/.env
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="${TELEGRAM_ALLOWED_USERS%%,*}" \
    -d text="✅ Slack surface SHIPPED. Try me in #eleva-$w."
done'
```

**Step 2: From the Slack side, each bot posts a "Hello from Slack" message into its dedicated channel as confirmation.**

**Step 3: Final summary in chat to Harv: which channels, what works, where docs landed, any deferred items.**

---

## Deferred (out of scope for this plan)

- **Systemd units** — bots stay tmux-based. Mirror OpenClaw systemd-user-service pattern across all 4 sisters in a future ship.
- **Multi-turn conversations** — Slack `thread_ts` keyed `claude --resume` could enable threaded coherence. Stateless per-message for now.
- **Cross-surface conversation continuity** — start TG, continue Slack. Out of scope.
- **TTS cost monitoring dashboard** — manual ElevenLabs usage check for now.

---

## Risk register

| Risk | Mitigation |
|---|---|
| `slack-bolt` import fails on Eleva | Task 4 verifies before any code change. |
| Threading deadlock on `_claude_lock` | Lock is held only during subprocess.run; max 600s timeout. |
| Slack Socket Mode silently disconnects | `SocketModeHandler` auto-reconnects; `*-bot-loop.sh` catches process death. |
| Token leak in stack trace | `_scrub()` strips `xox[bap]-` patterns before logging. |
| Refactor breaks Telegram | Task 8 has Telegram regression smoke before adding Slack code; ≥24h watch at Phase 4 gate. |
| Stray `school` in sed-clones | Task 15 Step 3 explicit grep audit (this was the gotcha from the original ship). |

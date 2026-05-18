# Eleva Sister Bots — Slack as Parallel Surface (Design)

**Status:** Design approved 2026-05-18. Implementation plan to follow via writing-plans.
**Scope:** All 4 sister workspaces on Eleva (Marketing, Open House, Web, School-Broker).
**Author:** Mac Claude (Opus 4.7) with Harv Balu.

## Context

Each Eleva sister workspace currently runs a Telegram bot (`@Eleva_RE_*_bot`) inside a tmux supervisor (`claud-<name>-bot`), with voice in (Groq Whisper) + voice out (ElevenLabs TTS) + stateless `claude -p` dispatch per message. Harv has Slack Premium and wants Slack as a parallel input/output surface — not a replacement for Telegram.

## Requirements (locked-in)

| Requirement | Decision |
|---|---|
| Scope | All 4 sister workspaces |
| Voice support | Voice + text on both surfaces (Slack + Telegram) |
| Channel model | One private channel per workspace (`#eleva-school`, `#eleva-marketing`, `#eleva-web`, `#eleva-openhouse`) |
| Allowlist | Harv only (mirror current Telegram security) |
| Slack app architecture | One Slack app per bot (4 total) — matches Telegram pattern, clean per-bot identity |
| Transport | Socket Mode (no public webhook needed — outbound WebSocket from Eleva) |

## Cost expectation

Marginal $ ≈ **zero**. Slack Premium already paid. Eleva VPS unchanged. Claude Max flat-rate. Voice (Groq + ElevenLabs) is per-use — only grows if usage grows. The real "cost" is engineering complexity (two listeners per bot, more code surface to maintain).

## Architecture

### Threading model per bot

Each `*-bot.py` becomes a **2-thread process** under the existing `*-bot-loop.sh` supervisor:

- **Thread T (Telegram):** the current long-poll loop, unchanged behavior.
- **Thread S (Slack):** new — `slack-bolt` Python `SocketModeHandler` (outbound WebSocket).

Both threads converge on a **surface-agnostic core**:

```
handle_message_core(
    env, surface, user_id, text, audio_bytes,
    reply_text_fn, reply_voice_fn,
)
```

The core does: allowlist check → optional Whisper transcribe → command handlers → `run_claude(...)` → reply (voice if input was voice, else text). Surface-specific I/O lives in thin wrappers passed in as `reply_text_fn` / `reply_voice_fn`.

### Concurrency

`run_claude()` is wrapped in a `threading.Lock()`. Concurrent `claude -p` subprocesses in the same workspace could collide on file edits, so the second request waits. Cheap insurance against accidental concurrent use across surfaces.

### Identity

One Slack app per workspace. Each appears as its own bot in its dedicated channel:

| Workspace | Channel | Slack bot name |
|---|---|---|
| Marketing | `#eleva-marketing` | Eleva Marketing Bot |
| Open House | `#eleva-openhouse` | Eleva Open House Bot |
| Web | `#eleva-web` | Eleva Web Bot |
| School-Broker | `#eleva-school` | Eleva RE School Bot |

### Crash recovery

Each listener thread is wrapped in try/except — one listener crashing is caught and logged without killing the other. Hard process death (segfault, OOM) is still caught by `*-bot-loop.sh`, which respawns the whole process. Bot state persists in `~/.<workspace>/bot-state.json` (existing file, gains a new key for Slack seen-event IDs because Socket Mode replays events on reconnect).

## Slack app config (×4)

Built once via Slack app manifest YAML; Harv pastes each into api.slack.com → "From manifest" → installs → grabs tokens.

### Socket Mode

**On.** Generates an App-level token (`xapp-...`). Enables outbound WebSocket — no public HTTP endpoint needed on Eleva.

### Bot OAuth scopes

- `chat:write` — send messages
- `files:write` — upload TTS voice replies
- `files:read` — download user voice uploads for Whisper
- `groups:history` — read messages in private channel
- `groups:read` — channel metadata
- `im:history` + `im:read` — fallback DM support (currently denied by channel allowlist, kept for future)
- `users:read` — resolve user IDs in allowlist

### Event subscriptions (over Socket Mode)

- `message.groups` — channel messages (primary path)
- `message.im` — DMs (denied by channel allowlist but logged)
- No `app_mention` needed — channel is dedicated, plain messages trigger

### Install → tokens

Install to workspace generates the Bot User OAuth Token (`xoxb-...`). Together with the App-level token (`xapp-...`), each bot has 2 tokens to paste into its `.env`.

## Voice on Slack

Slack has no native "voice message" primitive like Telegram. Voice = file uploads with audio MIME type.

### Voice IN (user → bot)

- Slack desktop / iOS / Android has a "record audio" button → recordings arrive as `message` events with `subtype: file_share` and `files: [{mimetype: "audio/..."}]`.
- File hosted on Slack's private CDN. Download requires `Authorization: Bearer <bot_token>`.
- Existing `transcribe_with_groq()` works as-is — Whisper accepts m4a/ogg/mp3/webm. Slack's native format is m4a (no conversion).

### Voice OUT (bot → user)

- Existing `tts_with_elevenlabs()` produces MP3.
- **Skip the MP3→OGG ffmpeg step** that Telegram needs — Slack accepts MP3 natively and renders an inline player.
- Upload via `client.files_upload_v2(channels=channel_id, file=mp3_path, title="Voice reply")`.

### Cost note

Voice replies double TTS spend potential if used heavily across both surfaces. `TTS_MAX_CHARS = 1500` cap still applies per reply. Monitor ElevenLabs usage post-rollout.

### Audit trail

Slack channels keep permanent history. Voice notes stay until manually deleted. Anything sensitive said via voice is preserved in channel history. (Worth flagging — Telegram's chat behaves similarly but the perception may be different.)

## Code structure

Each `*-bot.py` grows from ~393 lines (Telegram-only) to ~550 lines (+40%). Most of the addition is the Slack adapter; the core extraction is moving code around, not rewriting.

```
# === SHARED ===
read_env, log, load_state, save_state         # state.json gains slack_seen_ts[]
run_claude()                                  # unchanged + threading.Lock wrapper
transcribe_with_groq()                        # unchanged
tts_with_elevenlabs()                         # unchanged

# === SURFACE-AGNOSTIC CORE === (extracted from current handle_message)
handle_message_core(
    env, surface, user_id, text, audio_bytes,
    reply_text_fn, reply_voice_fn,
)

# === TELEGRAM ADAPTER === (existing code, lightly rewired)
tg_api, tg_send_message, tg_send_voice, tg_download_file, mp3_to_ogg
tg_listen()                                   # current main loop, calls _core

# === SLACK ADAPTER === (new, ~120 lines)
slack_send_message(client, channel, text)
slack_send_voice(client, channel, mp3_bytes)  # files_upload_v2, no OGG
slack_download_audio(client, file_id)         # auth-gated CDN download
slack_handle_event(env, client, event)        # filter, dispatch to _core
slack_listen()                                # SocketModeHandler(...).start()

# === MAIN ===
threading.Thread(target=tg_listen, daemon=True).start()
threading.Thread(target=slack_listen, daemon=True).start()
# main thread joins / handles signals
```

### Dependency added

`slack-bolt` (Python lib). Pure-Python, no native deps. `pip3 install --user slack-bolt` once on Eleva (shared by all 4 bots).

## Env vars & security

### New vars per `~/.<workspace>/.env` (mode 600)

```bash
SLACK_BOT_TOKEN=xoxb-...           # Bot User OAuth Token
SLACK_APP_TOKEN=xapp-...           # App-level token (Socket Mode)
SLACK_ALLOWED_USERS=U01234ABCD     # Harv's Slack user ID (comma-sep if expanded)
SLACK_CHANNEL_ID=C01234ABCD        # The workspace's dedicated channel ID
```

### Two-layer access check (defense in depth)

Every Slack event must pass BOTH checks or it's silently dropped + logged:

1. **Channel allowlist:** `event["channel"] == env["SLACK_CHANNEL_ID"]`.
2. **User allowlist:** `event["user"] in env["SLACK_ALLOWED_USERS"]`.

This is stricter than Telegram (user-only allowlist). Justified because Slack has more accidental-exposure surfaces (shared channels, DMs, mentions in other channels).

### Token transfer

Per the new `feedback-secret-transfer-via-terminal-not-chat.md` rule: tokens are pasted via a one-block `ssh -t eleva "cat >> ~/.<workspace>/.env" <<<...` pattern in Harv's terminal. Never in chat. Verify presence via `grep -c "SLACK_" ~/.<workspace>/.env`. Never echo values.

### Token leak prevention

Slack SDK occasionally surfaces auth header in stack traces. Wrap auth calls in try/except that scrubs `xoxb-*` / `xapp-*` patterns from caught exceptions before logging.

## Rollout sequence

### Pilot: School-Broker first

Smallest workspace, freshest ship (today). Lowest risk surface to discover Slack-specific gotchas. After pilot is green ≥24h, clone to remaining 3 sisters via sed pattern.

### Per-bot rollout steps (~30 min pilot, ~10 min each clone)

1. Build Slack app manifest YAML → Harv pastes into api.slack.com → "Create from manifest".
2. Install app to Slack workspace → grab `xoxb-` + `xapp-` tokens.
3. Create `#eleva-<name>` private channel → invite the bot → grab channel ID.
4. Harv pastes tokens into Eleva via the prepared secure terminal block.
5. (Pilot only) `ssh eleva 'pip3 install --user slack-bolt'`.
6. Backup existing bot: `cp ~/.<name>/scripts/<name>-bot.py ~/.<name>/scripts/<name>-bot.py.bak-v2-pretslack`.
7. Update `~/.<name>/scripts/<name>-bot.py` with refactored code (Section 4 of design).
8. Restart `claud-<name>-bot` tmux session. Tail `~/.<name>/logs/bot.log` for `START` lines from both threads.

### Smoke test checklist per bot

| Test | Expected | Proves |
|---|---|---|
| Text in `#eleva-<name>` | Text reply ≤30s | Slack core path |
| Voice note in `#eleva-<name>` | Voice reply (inline waveform) + text alongside | Whisper + ElevenLabs on Slack |
| DM the bot directly | Silent drop; log shows "channel mismatch" | Channel allowlist works |
| Text TG + Slack simultaneously | Both reply; second ~30s later | `run_claude()` lock serializes |
| `kill -9` the python process | `*-bot-loop.sh` respawns ≤5s; both surfaces back | Crash recovery still works |
| Telegram-only path | Identical behavior to pre-Slack | No regression |

### Clone phase (after pilot green ≥24h)

Sed pattern across 3 remaining bots:

```bash
ssh eleva 'for w in marketing web openhouse; do
  cp ~/.school/scripts/school-bot.py ~/.$w/scripts/$w-bot.py.slack-template
  # Then run targeted sed: s/SCHOOL_WORKDIR/MARKETING_WORKDIR/g, etc.
done'
```

Per-bot smoke runs all 6 tests after each clone.

### Rollback plan

Per-bot rollback is trivial:

```bash
ssh eleva 'cp ~/.<name>/scripts/<name>-bot.py.bak-v2-pretslack ~/.<name>/scripts/<name>-bot.py'
ssh eleva 'tmux send-keys -t claud-<name>-bot C-c; tmux send-keys -t claud-<name>-bot "~/.<name>/scripts/<name>-bot-loop.sh" Enter'
```

Telegram-only restored. Slack channel sits empty without harm. Per-bot blast radius means a broken pilot doesn't touch the other 3 sisters.

## Open questions / deferred

- **Multi-turn conversations** — current design stays stateless (per-message `claude -p`). Slack threading could naturally key on `thread_ts` for `claude --resume` later. Deferred.
- **Cross-surface conversation continuity** — start a thread on Telegram, continue on Slack? Out of scope v1.
- **TTS cost monitoring dashboard** — no automated tracking yet. Add if voice usage grows.
- **Systemd units** — bots still tmux-based. Mirror OpenClaw systemd-user-service pattern across all 4 sisters together as separate ship.

## Memory cross-refs

- Topic: `project-eleva-school-broker-claude.md`, `project-eleva-web-claude.md`, `project-eleva-marketing-claude.md`, `project-eleva-openhouse-claude.md`
- Rule: `feedback-secret-transfer-via-terminal-not-chat.md` (gates token handoff)
- Rule: `feedback-sync-verification-md5-not-counts.md` (applies if we sync any new files)

## Next step

Invoke `writing-plans` skill to produce a step-by-step implementation plan from this design.

---
name: harv-openclaw
description: "Manage OpenClaw (Eleva VPS) from Mac and from the n8n VPS. Status, version updates, restarts, config edits, Telegram group config, real cron scheduling, Hostinger snapshots, and a 6-check verify suite. Trigger: 'openclaw status', 'is eleva up', 'update openclaw', 'restart openclaw', 'edit openclaw config', 'set eleva group X', 'schedule eleva', 'snapshot eleva', 'verify eleva', or /harv-openclaw."
---

# harv-openclaw

Operations skill for managing **OpenClaw** — the agent orchestrator running on the **Eleva VPS** (Hostinger, `2.24.29.70`, user `harvey`, port `63988`, key-only auth). Works from Mac (Claude Code session) AND from the n8n VPS (`claud-ops` tmux session) by adapting commands via `env-detect.sh`. On Mac, `ssh eleva` uses Mac's own ed25519 key. On n8n VPS, `ssh eleva` uses the bridge keypair set up at `~/.ssh/eleva` (see Phase 2 of the implementation plan).

## Routing

Detect which capability the user wants from their request:

| User says... | → Section |
|---|---|
| "openclaw status", "is eleva up", "eleva health", "check eleva" | **A. Status** |
| "update openclaw", "bump eleva", "openclaw to latest" | **B. Update** |
| "restart openclaw", "restart eleva gateway", "kick openclaw" | **C. Restart** |
| "edit openclaw config", "set eleva `<key>`", "change `<key>` in openclaw" | **D. Config edit** |
| "set eleva group X", "change requireMention", "allowFrom", "groupPolicy" | **E. Telegram group config** |
| "schedule eleva", "openclaw cron", "make eleva do X every Y" | **F. Schedule cron** |
| "snapshot eleva", "back up openclaw", "hostinger snapshot" | **G. Snapshot** |
| "verify eleva", "is openclaw healthy", "verify state" | **H. Verify state** |

If ambiguous, ask the user which capability.

## Pre-flight (every section)

Before running any operational script:
1. On Mac: check warm SSH ControlMaster: `ssh -o BatchMode=yes eleva 'echo OK'`. Mac→Eleva is pubkey-only (no TOTP) and should always work; if it fails, investigate Mac SSH config / VPN before retrying. (`feedback-ssh-check-warm-controlmaster-first.md`)
2. On n8n VPS: the bridge keypair is at `~/.ssh/eleva_key` (note `_key` suffix — pre-existing from 2026-04-27 `vps-ops` setup). **n8n→Eleva requires TOTP** (`AuthenticationMethods publickey,keyboard-interactive` on Eleva sshd, gated by Match Address 100.108.90.54). The check `ssh -o BatchMode=yes eleva 'echo OK'` will fail with `Permission denied (keyboard-interactive)` if there's no warm ControlMaster. **First Eleva-touching command in a fresh `claud-ops` session prompts for Google Authenticator code**; subsequent ops within ~1 hour reuse the master via `ControlPersist 1h` in `~/.ssh/config`. This is intentional hardening, not a defect.
3. Confirm the user knows the section is about to mutate state if it does (Sections B, C, D, E, F, G).

## Safety discipline (non-negotiable)

1. **Snapshot before mutating updates** (Section B + G). Eleva-specific token `HOSTINGER_API_TOKEN_ELEVA` in `~/Library/CloudStorage/OneDrive-Personal/ClaudeCode/n8n/.env.secrets`, VPS ID `1379773`. GET first to surface any recent snapshot; POST replaces. (`feedback-prod-ops-snapshot-first.md`)
2. **Backup before config edits** (Section D + E). `.bak.YYYYMMDD-HHMMSS` suffix, same convention as harv-hermes.
3. **Stable channel only, NEVER beta** (Section B). Refuse `--beta` even if a newer beta is available. (`feedback-openclaw-never-beta.md`)
4. **Never echo tokens/keys on command lines** (Section G + any token-handling). Use temp file → read from file.

---

## Section A — Status

**Purpose:** Show current OpenClaw health: version, gateway state, team group config, uptime.

**Run:** `<skill-path>/scripts/eleva-status.sh`

The script auto-detects Mac vs VPS and always SSHes to `eleva` regardless (the alias resolves locally on each box). PATH is set inside the remote command so `openclaw` and `jq` resolve.

**Reading the output:**
- "OpenClaw 2026.5.X" → reports current version
- "active" under Gateway service → healthy
- Team group config keys (`groupPolicy`, `allowFrom`, `requireMention`, `messages.groupChat.visibleReplies`) — should match the live state baseline; surface any drift

If anything is off, recommend Section H (Verify state) for the full 6-check.

---

## Section B — Update

**Purpose:** Bump OpenClaw to the latest **stable** version safely.

**Steps:**

1. **Pre-flight:** check current version with Section A. Report it to user.
2. **Confirm intent:** "Update OpenClaw on Eleva from `<current-version>` to latest STABLE? This will take a Hostinger snapshot first, then `openclaw update --yes`, then verify. ~3-5 min total." Wait for explicit "yes."
3. **Snapshot (Section G):** GET first — if a recent snapshot exists, surface to user; POST replaces. Wait for "go ahead" before POST. **If Harv explicitly overrides snapshot-first (logged precedent on 2026-05-07 — see CHANGELOG), record the override in the report.**
4. **Upgrade:** `ssh eleva '~/.npm-global/bin/openclaw update --yes'`. Capture output. **Never pass `--beta`** even if upstream offers it.
5. **Restart gateway:** if `openclaw update --yes` didn't auto-restart cleanly, run Section C.
6. **Verify:** wait 5s, run Section H (full 6-check). Confirm new version, gateway active, all 4 team-handoff config keys preserved, Boolean(channel) bug count delta vs pre-upgrade.
7. **Report:** old version → new version, snapshot timestamp (or override note), `Boolean(channel)` count delta, any config drift.

**Abort conditions:**
- Snapshot fails AND Harv hasn't explicitly overridden → STOP.
- Update tries to install a beta/RC → STOP.
- Gateway doesn't come back active after restart → ALERT, recommend `ssh eleva 'journalctl --user -u openclaw-gateway -n 50'`.

---

## Section C — Restart

**Purpose:** Restart OpenClaw's gateway service.

**Run:** `<skill-path>/scripts/eleva-restart-gateway.sh`

The script:
1. SSHes to eleva.
2. `systemctl --user restart openclaw-gateway`.
3. Sleeps 3s.
4. Checks `is-active`. Exits non-zero if not active, with a pointer to `journalctl --user -u openclaw-gateway -n 30`.

**If restart fails:** check journalctl. Common causes: pnpm/npm state half-applied during an update, config syntax error from a recent edit (Section D's backup is your rollback).

---

## Section D — Config edit

**Purpose:** Surgically edit `~/.openclaw/openclaw.json` (or another file under `~/.openclaw/`) with backup-first discipline.

**Steps:**

1. **Identify target file:** usually `openclaw.json`. If user names a different file, use that.
2. **Show current value:** `ssh eleva "jq '<jq-path>' ~/.openclaw/openclaw.json"` (or grep for simpler cases).
3. **Confirm intent:** "Change `<path>` from `<old>` to `<new>` in `~/.openclaw/<file>`? This will back up the file with a timestamp suffix, then edit, then restart the gateway."
4. **Backup:** `<skill-path>/scripts/eleva-config-backup.sh <file>`. Confirm backup write succeeded. **Abort if backup fails.**
5. **Edit:** prefer jq for JSON (`ssh eleva "jq '<expr>' ~/.openclaw/openclaw.json > /tmp/oc.new && mv /tmp/oc.new ~/.openclaw/openclaw.json"`). Always re-read the file post-edit to verify before restarting.
6. **Diff:** `ssh eleva "diff ~/.openclaw/<file>.bak.<ts> ~/.openclaw/<file>"`. Show it to the user.
7. **Restart:** Section C.
8. **Verify:** Section A or H. Confirm gateway came back and config matches expectation.

**Common edits:**
- Team-handoff group config → use Section E (simpler, knows the knobs).
- Channel allowlists, persona files, agent defaults → here.

---

## Section E — Telegram group config

**Purpose:** Manage the known knobs that govern team-chat behavior, especially the "Harv's AI Team" group (`-1003974071850`).

**Background:** these are the keys that fixed the team-handoff Hem↔Eleva on 2026-05-06. Touching them without backups burns the handoff path.

**Knobs (all under `channels.telegram`):**

| Path | Current expected | Purpose |
|---|---|---|
| `.groupPolicy` | `"allowlist"` | Restricts groups OpenClaw responds in to the named allowlist |
| `.groups."-1003974071850".allowFrom` | `["5883909804", "8669022574"]` | Harv + Hem are the only senders OpenClaw responds to in the team chat |
| `.groups."-1003974071850".requireMention` | `false` | Eleva responds without explicit @-mention from Hem (paired with Hem's `requireMention: true` on the same group) |
| `.messages.groupChat.visibleReplies` | `"automatic"` | Eleva's replies are visible to Harv in the group |

**Steps:**

1. **Show current values** of the relevant key.
2. **Confirm intent.** Be specific about which key and what value.
3. **Backup:** `<skill-path>/scripts/eleva-config-backup.sh openclaw.json`.
4. **Edit via jq.** Always preserve the type (string vs bool vs array).
5. **Diff + Restart (Section C) + Verify (Section H).**

**Do NOT:**
- Flip `requireMention` back to `true` on Eleva without first flipping Hem's side back to `true` — both bots will go silent in the group (asymmetric gate kills the handoff).
- Remove `8669022574` (Hem) from `allowFrom` — that mutes Hem→Eleva.

---

## Section F — Schedule cron

**Purpose:** Add, edit, list, disable, or remove OpenClaw cron jobs via the gateway CLI.

**CLI overview** (from `openclaw cron --help`):

```
openclaw cron add        # add a job
openclaw cron edit       # patch fields of an existing job
openclaw cron list       # list jobs (use --all --json for full state)
openclaw cron disable    # soft-disable (preserves the job)
openclaw cron rm         # remove
openclaw cron show       # show one job
openclaw cron run        # fire now (debug)
openclaw cron runs       # run history
openclaw cron status     # scheduler status
```

**Working template pattern (per CHANGELOG 2026-05-09 + `feedback-diff-from-working-templates.md`):** Always start from a recently-shipped working cron, copy its shape, edit the deltas, then verify. Don't write a fresh `cron add` from scratch — small fields (e.g. `kind: at` ISO timezone offset, `delete-after-run`, `session` mode) are easy to get subtly wrong.

**Workflow:**

1. **Find a working template** from the recent CHANGELOG (e.g. `remind-twins-library-may11`, `remind-asha-ortho-jun7`). Read its full definition: `ssh eleva '~/.npm-global/bin/openclaw cron list --all --json | jq ".jobs[] | select(.name == \"<template-name>\")"'`.
2. **Show user the template + the diff** they're asking for (name, schedule, message, delivery).
3. **Confirm intent.**
4. **For one-shot reminders:** use `kind: at` + explicit ISO timestamp with `-07:00` (PDT) or `-08:00` (PST) offset.
5. **For recurring:** use cron-string syntax in `kind: cron`.
6. **Always include `delete-after-run: true` for one-shots** unless the user wants the job to persist for re-use.
7. **Message format:** wrap user-facing reminders with the literal-directive template: `SCHEDULED REMINDER FIRING. Reply with exactly this text and no preamble: "<actual user-facing text>"` — prevents the cron fire from being reinterpreted as a new request.
8. **Verify post-add:** `cron list --all --json | jq '.jobs[] | select(.name == "<new>")'` shows `enabled: true` + correct `nextRun`.

**Gotchas to surface to user:**
- `payload.message` is an instruction TO Eleva — paraphrased messages cause her to misinterpret the fire as a new request (Bug D, see CHANGELOG 2026-05-XX).
- `Boolean(channel)` bug (#9 in SESSION-STATE): cron-elevated-gate still present in 5.6 — do NOT pass `elevated: true` in cron prompts that run sudo; OS-layer NOPASSWD handles it.

---

## Section G — Snapshot

**Purpose:** Manage Hostinger snapshots of Eleva (1 snapshot slot per VPS — POST replaces existing).

**Run:** `<skill-path>/scripts/eleva-snapshot.sh [get|create]`

**Steps for a manual snapshot:**

1. `eleva-snapshot.sh get` — see current snapshot age. Hostinger keeps a single snapshot per VPS, auto-expires after ~20 days.
2. If recent (within last 24h), ask user if they want to replace.
3. `eleva-snapshot.sh create` — POST. Returns the new snapshot ID + timestamps.
4. Report ID, created_at, expires_at to user.

**Mac-only.** The token is intentionally NOT on either VPS (blast-radius reduction per `vps-ops` agent rules). If you're running from the `claud-ops` session on n8n VPS, this script will refuse and tell you to run from Mac.

**Restore path (manual):** Hostinger hPanel → VPS `srv1379773` → Snapshots → Restore. Eleva will reboot. Verify with Section A.

---

## Section H — Verify state

**Purpose:** Run the 6-check post-upgrade verify suite from `OpenClaw/kb/CHANGELOG.md` to confirm OpenClaw + Eleva persona config matches expected state.

**Pre-flight:** warm-CM check first.

**Commands (verbatim from CHANGELOG 2026-05-07 6-point sweep):**

```bash
# 1. Version
ssh -o BatchMode=yes eleva '~/.npm-global/bin/openclaw --version'
# Expected: OpenClaw 2026.5.6 (c97b9f7) — or whatever the current stable target is

# 2. Gateway active
ssh -o BatchMode=yes eleva 'systemctl --user is-active openclaw-gateway'
# Expected: active

# 3. groupPolicy
ssh -o BatchMode=yes eleva 'jq ".channels.telegram.groupPolicy" ~/.openclaw/openclaw.json'
# Expected: "allowlist"

# 4. Per-group allowFrom + requireMention
ssh -o BatchMode=yes eleva 'jq ".channels.telegram.groups.\"-1003974071850\"" ~/.openclaw/openclaw.json'
# Expected: allowFrom: ["5883909804","8669022574"], requireMention: false

# 5. Top-level visibleReplies
ssh -o BatchMode=yes eleva 'jq ".messages.groupChat.visibleReplies" ~/.openclaw/openclaw.json'
# Expected: "automatic"

# 6. Boolean(channel) cron-elevated-gate bug count (delta from pre-upgrade)
ssh -o BatchMode=yes eleva 'grep -c "Boolean(channel)" ~/.npm-global/lib/node_modules/openclaw/dist/sandbox-cli-*.js'
# Expected: same value as before last upgrade (i.e. unchanged 1 → 1 in 5.6). Surface delta.
```

For each command:
- Run it.
- Compare output to expected.
- Mark each line ✅ or ❌.

**Report:** if all 6 pass, "OpenClaw state matches CHANGELOG 2026-05-07 baseline (or current ref)." If any fail, drill into the specific drift before claiming healthy.

---

## Skill update procedure

If you (Claude) need to update this skill:
- Edit on Mac at `~/Library/CloudStorage/OneDrive-Personal/ClaudeCode/OpenClaw/harv-openclaw-skill/`.
- launchd will sync to n8n VPS within 30 min.
- For instant push: `~/Library/CloudStorage/OneDrive-Personal/ClaudeCode/OpenClaw/harv-openclaw-skill/scripts/sync-to-vps.sh`.
- DO NOT edit on VPS unless Mac is unavailable. If you do, manually `rsync` back from VPS to Mac.

## References

- Design doc: `OpenClaw/docs/plans/2026-05-10-harv-openclaw-skill-design.md`
- Implementation plan: `OpenClaw/docs/plans/2026-05-10-harv-openclaw-skill.md`
- OpenClaw workspace: `OpenClaw/SESSION-STATE.md`, `OpenClaw/kb/CHANGELOG.md`, `OpenClaw/kb/09-current-deployment.md`, `OpenClaw/CLAUDE.md`
- Memory: `feedback-openclaw-never-beta.md`, `feedback-prod-ops-snapshot-first.md`, `feedback-ssh-check-warm-controlmaster-first.md`, `feedback-launchd-fda-onedrive.md`, `feedback-diff-from-working-templates.md`, `project-openclaw-rebuild.md`
- Sister skill: `harv-hermes` (manages Hem on n8n VPS — same architecture)
- Sister agent: `vps-ops` (general Mac → VPS ops; complementary)

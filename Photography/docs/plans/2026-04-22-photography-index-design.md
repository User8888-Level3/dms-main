# Photography Index — Design Doc

**Date:** 2026-04-22
**Status:** Approved, ready for implementation plan
**Author:** Harv + Claude (brainstorming session)

## Goal

Build a browsable index of Harv's 19 TB / 100K+ photo archive on Synology (`smb://172.22.2.147/Pictures-Vol3`), with thumbnails, search, and duplicate detection. Harv never runs scripts — Claude operates everything.

## Scope

Phase 1: **year folders 2013 through 2025** only.
Phase 2 (later): topical folders (Asha, Babies, Fam, Cars, Gardening, Print, Drone, HarvBalu.com).
Phase 3 (later): backup/library folders (iPhone.photoslibrary, M1-MAC-Backup, OLD, Plex, #recycle) — these are the most likely duplicate sources, but we compare *against* a clean year index.

## Locked Decisions

| Question | Choice |
|---|---|
| Scope | Year folders 2013–2025 first (Q1.D) |
| Thumbnail storage | Hybrid: thumbs on Synology `.index/thumbs/`, HTML + SQLite local in `Photography/` (Q2.B+) |
| File types | Images + RAW (CR3/CR2/ARW/NEF/DNG) + Video (MP4/MOV/M4V) (Q3.D) |
| Browsing layout | Year-at-a-glance + global search + filters (Q4.D) |
| Indexing metadata | SHA-1 + pHash + full EXIF (Q5.B+C+D) |
| Implementation | Python indexer + static HTML output (Approach 1) |
| Operator | Claude runs all scripts; Harv's interaction is conversational |

## Architecture

```
Photography/
├── build_index.py           # indexer (run by Claude, not Harv)
├── .venv/                   # Python deps (Pillow, pillow-heif, imagehash, etc.)
├── index.db                 # SQLite, one row per file
├── site/                    # generated HTML — open site/index.html to browse
│   ├── index.html           # year grid + global search
│   ├── years/YYYY.html      # year-at-a-glance
│   ├── search.html
│   ├── duplicates.html
│   ├── photo/<sha1>.html    # full-size preview + EXIF
│   └── assets/              # css, js, search-YYYY.json (split by year)
├── logs/
│   ├── indexer.log
│   └── deletions.jsonl      # append-only audit
├── docs/plans/              # this doc + implementation plan
└── SESSION-STATE.md         # cross-session resume state

/Volumes/Pictures-Vol3/.index/thumbs/<year>/<event>/<sha1[:2]>/<sha1>.jpg
```

## Data Model (SQLite)

```sql
CREATE TABLE files (
  id              INTEGER PRIMARY KEY,
  path            TEXT NOT NULL UNIQUE,
  year            INTEGER,
  event_folder    TEXT,
  filename        TEXT,
  ext             TEXT,
  kind            TEXT,          -- image | raw | video
  bytes           INTEGER,
  mtime           REAL,          -- incremental skip key
  sha1            TEXT,
  phash           TEXT,          -- 16 hex chars (64-bit)
  width           INTEGER,
  height          INTEGER,
  exif_taken_at   TEXT,          -- ISO8601
  exif_camera     TEXT,
  exif_gps_lat    REAL,
  exif_gps_lon    REAL,
  thumb_rel       TEXT,
  indexed_at      REAL,
  deleted_at      REAL,          -- set when moved to #recycle
  error           TEXT
);

CREATE INDEX idx_files_year_event ON files(year, event_folder);
CREATE INDEX idx_files_sha1 ON files(sha1);
CREATE INDEX idx_files_phash ON files(phash);
CREATE INDEX idx_files_taken ON files(exif_taken_at);

CREATE TABLE dup_groups (
  id          INTEGER PRIMARY KEY,
  kind        TEXT,            -- exact | similar
  member_ids  TEXT,            -- JSON array
  reviewed    INTEGER DEFAULT 0,
  decision    TEXT
);
```

## Indexing Algorithm

**Phase 1 (discovery):** walk year folders, collect paths, stat each, compare mtime against DB, queue new/changed files.

**Phase 2 (processing, 12-thread pool):** per file —
1. Read bytes once over SMB.
2. SHA-1 of bytes.
3. Decode:
   - JPG/PNG/HEIC → Pillow (`pillow-heif` plugin for HEIC).
   - CR3/raw → `exiftool -b -PreviewImage` → Pillow. Fallback to `rawpy`.
   - Video → `ffmpeg -ss 1 -vframes 1 -f image2pipe` → Pillow.
4. pHash (imagehash), width, height, 400 px JPEG thumbnail at quality 82.
5. EXIF (taken-at, camera, GPS) via Pillow + piexif, or exiftool for raw/video.
6. Write thumb to Synology: `.index/thumbs/<year>/<event>/<sha1[:2]>/<sha1>.jpg`.
7. UPSERT row. Batch commits every 100 files.

**Concurrency:** `ThreadPoolExecutor(12)`. Network-bound, GIL is fine. Single writer thread owns SQLite connection.

**Error handling:**
- Corrupt/unreadable → row with `error=<reason>`, keep going.
- SMB retry 3× with backoff. On 50+ consecutive SMB errors → pause 60 s, verify mount, bail cleanly if gone.
- SIGINT → finish current file, commit, exit. Resumable.

**Progress:**
- Log per 100 files: `[2024/20241030-New Orleans] 847/12,043 (7%) — 45 files/sec — ETA 4m 12s`.
- SESSION-STATE.md rolling summary every 1,000 files.

**Throughput estimate:** 20–60 files/sec over gigabit LAN. 100K-file archive → 1–3 hours.

## Thumbnail Specs

| Type | Decode path |
|---|---|
| JPG, PNG, HEIC | Pillow + `ImageOps.exif_transpose` for orientation |
| CR3, CR2, ARW, NEF, DNG | `exiftool -b -PreviewImage` → Pillow (rawpy fallback) |
| MP4, MOV, M4V | `ffmpeg -ss 1 -vframes 1` → Pillow; overlay play-icon in corner |

**Output:** 400 px long edge, JPEG q82 progressive, ~30–60 KB each. Path uses sha1 prefix to keep directories small.

## HTML Output

| Page | Content |
|---|---|
| `index.html` | Year grid (2013–2025), cover tile + count per year, global search bar |
| `years/YYYY.html` | All photos for year, grouped by event folder with sticky headers, lazy-loaded grid |
| `search.html` | Filtered results (filename, event, date range, kind: filters) |
| `duplicates.html` | Dup groups, sorted by potential savings |
| `photo/<sha1>.html` | Full thumbnail, EXIF panel, keyboard nav, Reveal-in-Finder |

- Dark theme, justified grid, no framework, no build step. Native `loading="lazy"`.
- Thumb URLs: `file:///Volumes/Pictures-Vol3/.index/thumbs/...`. Broken if mount disconnected (acceptable).
- Search JSON split by year (`search-YYYY.json`, 2–5 MB each) to avoid a 20 MB monolith.
- Search fields: filename, event, year, date, camera. Filters: `kind:video`, `kind:raw`, `has:gps`, `sha1:`.

**Explicitly NOT building:** face recognition, map view, tagging, rating, edit tools.

## Duplicate Detection

**Exact:** `GROUP BY sha1 HAVING COUNT(*) > 1` — bit-identical files.

**Similar:** pHash Hamming distance ≤ 4 (default, tunable via `--threshold`). Catches compression/resize variants, raw+JPG pairs, crop variants.

**duplicates.html:**
- Groups sorted by `sum(bytes) - max(bytes)` — biggest space wins first.
- Thumbnails side by side per group. Each shows: path, dimensions, bytes, EXIF date, ext.
- Auto-picked "keeper" highlighted green (heuristic: largest resolution > raw > most-original path > earliest EXIF). Losers red.
- Per-group: **Keep all** · **Accept keeper** · **Pick different keeper**. Decisions exported as `decisions.json`.

## Deletion Workflow

Never auto-deletes. Moves to `#recycle`, never `rm`.

1. Harv reviews groups in browser, clicks decisions.
2. Exports `decisions.json`.
3. Harv says "apply the decisions."
4. Claude loads JSON, shows count + size summary, asks for explicit approval.
5. On yes: `mv` each loser into `/Volumes/Pictures-Vol3/#recycle/dup-cleanup-YYYY-MM-DD/<preserve/path/>`.
6. DB updated: `deleted_at` set, rows hidden from views but kept for audit.
7. Every action logged to `logs/deletions.jsonl` (append-only).

**Safety rails:**
- `--dry-run` always run first.
- Refuses to delete from un-indexed folders.
- Dated `#recycle` subfolders preserve original paths.

## Session Handoff Protocol

**File:** `Photography/SESSION-STATE.md`, updated at every major checkpoint.

**Contains:** where we are, decisions locked, in-flight PIDs/logs, open questions, one-line resume prompt, pointers to this doc and the plan.

**Trigger:** at ~60% context usage, Claude proactively writes a full handoff and tells Harv: *"Context is getting heavy. Start a fresh session and say 'continue photography index' — I'll pick up from SESSION-STATE.md."* Memory pointer in MEMORY.md means any future Claude session can find this project.

Also applies cross-project per [feedback-context-60-percent-checkpoint.md](../../../../.claude/projects/-Users-harvinderbalu1-Library-CloudStorage-OneDrive-Personal-ClaudeCode/memory/feedback-context-60-percent-checkpoint.md).

## Out of Scope (Phase 1)

- Indexing topical/backup folders (phase 2/3).
- Face recognition, map view, tagging, rating, edit tools.
- Auto-deletion without explicit approval.
- Live/server-based browsing (static HTML is enough for now; Flask can come later).
- Cross-device sync of thumbnails (they live on Synology, usable from anywhere with mount).

# Photography Index — Session State

**Last updated:** 2026-07-16 (dashboard repaired + "Light Table" redesign shipped)
**Phase:** Feature-complete. Ongoing operations only.

---

## 2026-07-16 — dashboard repair + redesign (read before touching the site)

**Google Drive strips symlink targets in this folder.** It zeroed both `site/thumbs` and
`.venv/bin/python*`, which killed every thumbnail and stopped the server from launching.
Expect this to recur.

- `photo_server.py` now serves `/thumbs/` **directly from `config.THUMB_ROOT`**, so the
  `site/thumbs` symlink is no longer load-bearing. It also sends `Cache-Control`
  (`no-cache` for pages, 1-year immutable for SHA-1-addressed thumbs) — before this,
  browsers showed days-stale pages after every regeneration.
- If the venv dies: relink `python{,3,3.13}` → `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13`.
- **Open via `Photo-Dashboard.command`, never `file://`** — search + Open File/Folder need the server.

**"Light Table" redesign** — graphite `#08090b` + focus-peaking lime `#cdf24c`,
Bricolage Grotesque / Instrument Sans / Geist Mono, AF corner-bracket tile hovers,
`FR 01` EXIF chips. Done in `photo_index/templates/` then regenerated (index + 13 year
pages); `duplicates.html` inherits it via the shared stylesheet.

⚠️ **CSS landmine:** never combine `background-attachment: fixed` with a blurred sticky
header — that pair black-screens Chrome's compositor on macOS. The current CSS avoids
both; grain is a fixed-position pseudo-element instead.

⚠️ **Uncommitted:** these changes are working-tree only. Committing is recommended given
Google Drive's track record in this folder.

Full writeup: `session-2026-07-16-photo-archive-redesign.md` (GoogleDrive-ClaudeCode memory)
· OneNote **Photography → Claude-Photo**.

---

## PICKUP NOTE (read this first, future-me)

Project is done. No active work.

If Harv says *"continue photography index"*, he almost certainly wants one of these:

1. **"Re-index / include new photos"** → `./.venv/bin/python build_index.py index /Volumes/Pictures-Vol3/<year> --workers 12`. mtime-skip is cheap; re-running on existing years is almost free.
2. **"Run dedup again"** → `build_index.py decide --out decisions.json` → inspect → `apply decisions.json --apply`. The 2,928 remaining similar clusters will still be there waiting for visual review.
3. **"Open the dashboard"** → Run `Photography/Photo-Dashboard.command` (double-clickable) OR start the server yourself: `cd Photography/site && ../.venv/bin/python -m http.server 8765 --bind 127.0.0.1`, then open http://127.0.0.1:8765/.
4. **"Purge #recycle"** → `rm -rf "/Volumes/Pictures-Vol3/#recycle/dup-cleanup-2026-04-23"` (~52.1 GB). **ASK FIRST** — this is destructive. Everything in there was moved by this project.
5. **Phase 2 scope expansion** → point indexer at topical folders (Asha, Drone, Fam, etc.) or library sources (iPhone.photoslibrary, M1-MAC-Backup). Schema already supports cross-source dedup.

**Before touching code:** `./.venv/bin/pytest tests/ -q` — should be 41 passing.

**Known gotcha:** Harv uses OneNote in dark mode. If you generate any OneNote page, NEVER put `background:` on a `<table>` wrapper — only on specific header cells, always paired with explicit light `color:`. Body cells stay transparent so OneNote's theme handles contrast. See `feedback-onenote-dark-mode.md` in memory.

**Orphan to ignore:** the empty `Computers > Photography` section in OneNote was a mistake I made on 2026-04-23. Harv was going to delete it manually (Graph API can't delete sections). Don't recreate it — Harv's real notebook is **Photography > Claude-Photo**.

---

## Where we ended up

**26,438 files indexed** across 2013–2025 (6 errors, all Synology-side file corruption).
**23,811 active** after dedup.
**2,621 files moved to `#recycle`** (~52.1 GB reclaimable).
**41 tests passing.**

### Per-year indexing timing (M3 run, 2026-04-22/23)

| Year | Files | Time | Rate |
|---|---|---|---|
| 2013 | 874 | 2m56s | 4.9/s |
| 2014 | 1,258 | 6m02s | 3.5/s |
| 2015 | 835 | 12m33s | 1.1/s |
| 2016 | 4,367 | 28m11s | 2.6/s |
| 2017 | 2,149 | 11m54s | 3.0/s |
| 2018 | 278 | 1m11s | 3.9/s |
| 2019 | 835 | 4m22s | 3.2/s |
| 2020 | 1,830 | 47m51s | 0.6/s |
| 2021 | 2,695 | 18m48s | 2.4/s |
| 2022 | 5,493 | 30m27s | 3.0/s |
| 2023 | 3,481 | 27m28s | 2.1/s |
| 2024 | 1,790 | 16m56s | 1.8/s |
| 2025 | 553 | 4m33s | 2.0/s |
| **Total** | **26,438** | **~3h13m** | **2.3/s avg** |

### Dedup cleanup passes

| Pass | Exact groups | Similar raw+JPG | Files moved | Space |
|---|---|---|---|---|
| 1 | 1,974 | 222 | 2,563 | 51.46 GB |
| 2 | 0 | 58 | 58 | 651.7 MB |
| **Total** | **1,974** | **280** | **2,621** | **~52.1 GB** |

### What's left in `duplicates.html` (2,928 similar groups not auto-touched)

| Category | Groups | Why skipped |
|---|---|---|
| sequential_pair | 855 | Sequential captures — likely distinct frames |
| other | 802 | Mixed, ambiguous |
| video_burst_small | 387 | 2–3 videos per group |
| sequential_small_burst | 319 | 3–5 burst frames |
| cross_year | 216 | pHash false positive likely |
| video_burst_large | 129 | 4+ videos |
| cross_event | 113 | Same file copied across folders |
| sequential_medium_burst | 80 | 5–15 burst frames |
| sequential_large_burst | 6 | 15+ burst frames |

These need human eyes — auto-deleting bursts or cross-year matches would risk real content loss.

---

## Accessing the dashboard

**Easy (double-click, recommended):** `Photography/Photo-Dashboard.command` — starts the HTTP server and opens the browser. Keeps running until you close its Terminal window. First run requires right-click → Open to bypass macOS Gatekeeper.

**Manual:**
```bash
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/Photography/site
../.venv/bin/python -m http.server 8765 --bind 127.0.0.1
# then open http://127.0.0.1:8765/
```

**Direct file:// (limited):** open `site/index.html` directly in Safari. Year pages + thumbnails work, but **global search breaks** because fetch() is CORS-blocked on `file://`.

Stop server: `pkill -f "http.server 8765"`.

---

## Commands reference

```bash
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/Photography

# Index new photos (incremental)
./.venv/bin/python build_index.py index /Volumes/Pictures-Vol3/<year> --workers 12

# Limit to first N files (smoke tests)
./.venv/bin/python build_index.py index /Volumes/Pictures-Vol3/<year> --limit 50 --workers 4

# Regenerate site + search JSON + duplicates.html
./.venv/bin/python build_index.py html

# Skip duplicates.html regen (faster during indexing)
./.venv/bin/python build_index.py html --no-dups

# Auto-decide dup groups
./.venv/bin/python build_index.py decide --out decisions.json

# Dry-run apply
./.venv/bin/python build_index.py apply decisions.json

# Real apply (destructive, moves to #recycle)
./.venv/bin/python build_index.py apply decisions.json --apply

# Tests
./.venv/bin/pytest tests/ -q
```

**Nuclear reset (erases all index state but NOT the source photos):**
```bash
rm index.db index.db-wal index.db-shm
rm -rf /Volumes/Pictures-Vol3/.index/thumbs
rm -rf site/years site/photo site/assets/search-*.json
```

---

## Decisions locked (for any v2 continuation)

See `docs/plans/2026-04-22-photography-index-design.md`. Summary:

- **Scope phase 1:** year folders 2013–2025 only.
- **Thumbs on Synology:** `/Volumes/Pictures-Vol3/.index/thumbs/<year>/<event>/<sha1[:2]>/<sha1>.jpg` (944 MB used).
- **Metadata DB:** local SQLite at `Photography/index.db`, WAL mode.
- **File types:** JPG/PNG/HEIC (Pillow) + CR2/DNG (Pillow native) + CR3/ARW/NEF/ORF/RW2 (exiftool preview) + MP4/MOV (ffmpeg frame grab).
- **Captured:** SHA-1 + pHash + full EXIF in one pass.
- **Threaded indexer:** 12-worker `ThreadPoolExecutor` + single-writer SQLite thread, 100-row batched commits.
- **Retry:** `@smb_retry()` 3 attempts, 2s exponential backoff on `OSError` + `TimeoutExpired`.
- **Deletions:** never `rm`; always `mv` to `#recycle/dup-cleanup-YYYY-MM-DD/` with numeric `__dupN` collision suffix. DB `deleted_at` set. Append-only `logs/deletions.jsonl`.

---

## Pending housekeeping for Harv (his call, no rush)

- [ ] **Purge `/Volumes/Pictures-Vol3/#recycle/dup-cleanup-2026-04-23/`** once confident (~52.1 GB).
- [ ] **Manual review the 2,928 remaining similar clusters** via `duplicates.html` — export decisions.json → `apply --apply`.
- [ ] **Delete the empty orphan section** `Computers > Photography` in OneNote client (Graph API can't; I already deleted my misplaced page from it).
- [ ] **Fix/relocate 6 corrupted 2016-07-16 files** on Synology (3 CR2 with malformed XMP, 2 CR2 all-binary-zeros, 1 MOV missing moov atom). Synology-side damage, not our bug.

---

## Commits on main branch (User8888-Level3)

| SHA | Milestone |
|---|---|
| `058c140` | M1+M2 — threaded indexer + 2024 archive |
| `28181a1` | M2 docs — SESSION-STATE handoff |
| `458e458` | M3 — full archive + search UI |
| `f412140` | M4 — duplicate detection + review UI |
| `8802e68` | auto-decide + apply_decisions (M5 Tasks 24-26) |
| `509935e` | M5 pass 1 — 2,563 dups moved (51.5 GB) |
| `a820558` | M5 pass 2 — 58 more raw+JPG pairs (+651.7 MB) |

---

## Pointers

- Design doc: `docs/plans/2026-04-22-photography-index-design.md`
- Implementation plan: `docs/plans/2026-04-22-photography-index.md`
- Memory pointer: `project-photography-index.md` in Claude auto-memory.
- OneNote record: **Photography notebook > Claude-Photo section** (NOT Computers > Photography).
- Data source: `smb://172.22.2.147/Pictures-Vol3` (24 TB, 19 TB used, mounted at `/Volumes/Pictures-Vol3`).
- Dashboard launcher: `Photo-Dashboard.command` (double-clickable).

# Photography Index — Session State

**Last updated:** 2026-04-22 (M1 + M2 + M3 COMPLETE — ready for M4 dup detection)
**Phase:** Ready for M4 (exact + similar duplicate detection, `duplicates.html`).

## Where we are

**M1 COMPLETE.** 40 CR2 raws from 2023/20230101-SanJose-XO indexed with site generated.

**M2 COMPLETE.** 2024 indexed end-to-end: **1790 files, 0 errors, 16m56s (1.8/s)**. Committed as `058c140`.

**M3 COMPLETE.** Full 13-year archive indexed: **26,438 files across 2013–2025, 6 errors** (all file corruption on Synology, not our bug — 3 CR2 with XMP errors, 2 CR2 all-zero, 1 MOV missing moov atom). Breakdown: 6,871 images + 14,194 raws + 5,373 videos. Top cameras: Canon EOS REBEL T5i (13,958), Canon EOS RP (3,551), PowerShot SX230 HS (1,446), Rebel XT (1,242), DJI drone (130), iPhones (~150). Search UI + JSON exports live.

### Per-year timing

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

**Added in M2:**
- `make_thumbnail_raw()` — CR3/ARW/NEF/ORF/RW2 via exiftool preview extraction (tries PreviewImage → JpgFromRaw → ThumbnailImage).
- `make_thumbnail_video()` — ffmpeg frame at t=1s with t=0 fallback.
- `extract_exif_exiftool()` — JSON-mode exiftool for CR3/MP4/MOV (piexif can't read ISO-BMFF).
- Dispatcher in `indexer.py` routes by `kind`/`ext`: CR2/DNG stay on Pillow (fast), CR3+ go to exiftool, videos to ffmpeg. Fall back to exiftool preview if Pillow fails on a raw.
- `photo_index/runner.py` — 12-worker `ThreadPoolExecutor` + single-writer SQLite thread, 100-row batched commits, WAL mode.
- `photo_index/retry.py` — `@smb_retry()` (3 attempts, 2s exponential backoff), applied to hash + thumb + exif hot paths.
- `photo_index/progress.py` — `ProgressLogger` (per-row JSONL + interval stdout lines with ETA).
- `build_index.py` rewired with `--workers` flag + SIGINT → `stop_event` (drains then exits cleanly; second SIGINT force-quits).
- Fixed "Canon Canon EOS RP" → "Canon EOS RP" via `_join_camera()`. Cleaned 50 existing DB rows.

**30 tests passing** (was 13 at M1 end). +17 tests: 5 retry, 4 runner (incl. stop_event), 3 progress, 2 thumb (raw+video), 2 indexer dispatch, 1 camera-join.

**Smoke-tested** the threaded pipeline on 10 mixed CR3/MP4 files from 2024: 10/10 ok in 27s (~0.4/s — 4 workers).

## In-flight

Nothing running. M2 committed, tests green, site regenerated.

## How to rerun / extend

```bash
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/Photography
# Index any year (incremental — mtime-skips unchanged files):
./.venv/bin/python build_index.py index /Volumes/Pictures-Vol3/2024 --workers 12
# With limit (smoke tests):
./.venv/bin/python build_index.py index /Volumes/Pictures-Vol3/2024 --limit 50 --workers 4
# Regenerate site:
./.venv/bin/python build_index.py html
# Full test suite:
./.venv/bin/pytest tests/ -q
```

**To wipe and start over:** `rm index.db index.db-wal index.db-shm && rm -rf /Volumes/Pictures-Vol3/.index/thumbs && rm -rf site/years site/photo`.

## Decisions locked

See [docs/plans/2026-04-22-photography-index-design.md](docs/plans/2026-04-22-photography-index-design.md). Summary:

- **Scope:** year folders 2013–2025 only for phase 1.
- **Storage:** thumbnails on Synology at `/Volumes/Pictures-Vol3/.index/thumbs/`, HTML + SQLite local in `Photography/`.
- **File types:** JPG/PNG/HEIC + CR3/raw + MP4/MOV.
- **Layout:** year-at-a-glance HTML with global search, filters, and a separate duplicates page.
- **Indexing captures:** SHA-1 (exact dup), pHash (similar dup), full EXIF (date, camera, GPS).
- **Implementation:** Python indexer + static HTML. Claude runs all scripts — Harv never touches a CLI.
- **Deletion:** never `rm`; move to dated `#recycle/dup-cleanup-YYYY-MM-DD/` subfolder with append-only audit log.

## Open questions

None — design is fully approved.

## Next action

**Local HTTP server** is running on `http://127.0.0.1:8765/` (background task `bpsn8l2jh`). Kill via `pkill -f "http.server 8765"` when done.

**Harv:** browse the site at http://127.0.0.1:8765/ — 13 year tiles with covers, each year page works, and the search bar accepts queries like `year:2016 kind:video`, `camera:canon`, `has:gps`, `sha1:abc`, or free text. If it looks solid, say *"continue to M4"* to start duplicate detection.

**Claude (next session):** on "continue photography index" — read this file. Start M4 Task 21 (exact-match dup query via SHA-1 GROUP BY), then Task 22 (pHash similar-match with BK-tree or prefix-bucketing), then Task 23 (`duplicates.html` with keeper heuristic + localStorage decisions).

**Known data oddities to consider for M4:**
- 169 exact-dup SHA-1 collisions already found within 2024 alone. Full-archive dup count will be interesting.
- 6 error rows (year=2016) are garbage files on the Synology — flag them to Harv for possible recycle-bin move at some point.

## Remaining milestones

- **M4** (Tasks 21–24): Exact dup detection + pHash similarity, duplicates.html with keeper heuristic.
- **M5** (Tasks 25–27): Deletion workflow (`#recycle` moves, audit log, decisions.json).

## Pointers

- Design doc: `docs/plans/2026-04-22-photography-index-design.md`
- Implementation plan: `docs/plans/2026-04-22-photography-index.md`
- Memory pointer: `project-photography-index.md` in Claude auto-memory (cross-session discoverable).
- Data source: `smb://172.22.2.147/Pictures-Vol3` (24 TB, 19 TB used, mounted at `/Volumes/Pictures-Vol3`).

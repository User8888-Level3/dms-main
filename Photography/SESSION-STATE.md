# Photography Index — Session State

**Last updated:** 2026-04-22 (M1 + M2 COMPLETE — ready for M3)
**Phase:** Ready for M3 (all years 2013–2025 + search UI).

## Where we are

**M1 COMPLETE.** 40 CR2 raws from 2023/20230101-SanJose-XO indexed with site generated.

**M2 COMPLETE.** 2024 indexed end-to-end: **1790 files, 0 errors, 16m56s (1.8/s)**. 26 event folders, 1619 CR3 raws, 70 videos, 101 images, 1621 unique thumbs on Synology (28 MB). 169 exact byte-dupes surfaced naturally via SHA-1 collisions. Committed as `058c140`.

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

**Harv:** open `site/years/2024.html` and scroll. Expected: 1780 thumbnails grouped under 26 event folders, mix of photos and videos. If it looks good, say *"continue to M3"* to kick off the full 2013–2025 indexing run (background, expect 2–4 h) + search UI build.

**Claude (next session):** on "continue photography index" — read this file. If Harv approved, start M3 Task 18 (background run across 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2025; 2023 and 2024 already indexed). Then Task 19 (search JSON export) and Task 20 (search UI).

## Remaining milestones

- **M3** (Tasks 18–20): Index all 2013–2025, search JSON + search UI.
- **M4** (Tasks 21–24): Exact dup detection + pHash similarity, duplicates.html with keeper heuristic.
- **M5** (Tasks 25–27): Deletion workflow (`#recycle` moves, audit log, decisions.json).

## Pointers

- Design doc: `docs/plans/2026-04-22-photography-index-design.md`
- Implementation plan: `docs/plans/2026-04-22-photography-index.md`
- Memory pointer: `project-photography-index.md` in Claude auto-memory (cross-session discoverable).
- Data source: `smb://172.22.2.147/Pictures-Vol3` (24 TB, 19 TB used, mounted at `/Volumes/Pictures-Vol3`).

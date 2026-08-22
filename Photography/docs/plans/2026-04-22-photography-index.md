# Photography Index Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a browsable thumbnail index of Harv's 19 TB Pictures-Vol3 Synology archive (year folders 2013–2025), with metadata, search, and duplicate detection. Harv operates conversationally — Claude runs every script.

**Architecture:** Python indexer (`build_index.py`) walks SMB-mounted year folders, generates 400 px thumbnails to `/Volumes/Pictures-Vol3/.index/thumbs/`, stores SHA-1 + pHash + EXIF in local SQLite. Static HTML (year-at-a-glance + search + duplicates page) generated from DB. Deletions move to dated `#recycle/` subfolder, never `rm`.

**Tech Stack:** Python 3.11+, Pillow, pillow-heif, imagehash, exiftool (CLI), ffmpeg (CLI), SQLite (stdlib). Static HTML + vanilla JS, no build step.

**Full design:** [2026-04-22-photography-index-design.md](2026-04-22-photography-index-design.md)

---

## Environment notes (read before starting)

1. **OneDrive NFS git timeout** — `git status`/`commit` can hang on mmap. Use targeted `git add <paths>` and batched commits when OneDrive sync is quiet. If a commit fails, stage and defer; note in SESSION-STATE.md.
2. **SMB mount must be active** — `/Volumes/Pictures-Vol3` before running any indexer command. If the mount is gone, the indexer bails cleanly (designed for this).
3. **Claude operates everything** — every "Run:" below is for Claude's Bash tool, not Harv. Harv's only interactions are saying "run it" / "open the site" / "apply the deletions."
4. **Session state** — update `SESSION-STATE.md` after each milestone (M1…M5). Proactively checkpoint at ~60% context per `feedback-context-60-percent-checkpoint.md`.

---

## Milestones

| | Milestone | Exit criteria |
|---|---|---|
| **M1** | End-to-end on one event folder | `site/index.html` shows thumbnails for one small folder (~10–30 photos). DB populated. |
| **M2** | Full year 2024 indexed | All file types work (JPG/HEIC/CR3/MP4). Threaded. Year-at-a-glance HTML. Progress log. |
| **M3** | All years 2013–2025 indexed + search | Main index + per-year pages + search.json + filters. |
| **M4** | Duplicate detection | `duplicates.html` with exact + similar groups, keeper heuristic, decision export. |
| **M5** | Deletion workflow | `decisions.json` → `#recycle` moves with dry-run, audit log, DB update. |

Checkpoint/commit/SESSION-STATE update after each milestone.

---

# M1 — End-to-end on one event folder

**Purpose:** prove the whole pipe (walk → hash → decode → thumb → DB → HTML) works on a small test set before touching the full archive.

**Target folder for testing:** `/Volumes/Pictures-Vol3/2023/20230101-SanJose-XO` (small, JPG-only, confirmed to exist).

## Task 1: Project scaffolding

**Files:**
- Create: `Photography/build_index.py` (stub)
- Create: `Photography/photo_index/__init__.py`
- Create: `Photography/photo_index/config.py`
- Create: `Photography/photo_index/db.py`
- Create: `Photography/photo_index/walker.py`
- Create: `Photography/photo_index/hasher.py`
- Create: `Photography/photo_index/thumbs.py`
- Create: `Photography/photo_index/exifx.py`
- Create: `Photography/photo_index/indexer.py`
- Create: `Photography/photo_index/html_out.py`
- Create: `Photography/tests/__init__.py`
- Create: `Photography/tests/conftest.py`
- Create: `Photography/tests/fixtures/` (dir — will hold tiny test images)
- Create: `Photography/pyproject.toml`
- Create: `Photography/.gitignore`
- Create: `Photography/README.md`

**Step 1 — Create directory skeleton.**

Run:
```bash
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/Photography && \
mkdir -p photo_index tests/fixtures docs/plans logs site/years site/photo site/assets
```

**Step 2 — Write `pyproject.toml`.**

```toml
[project]
name = "photo-index"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "Pillow>=10.2",
  "pillow-heif>=0.16",
  "imagehash>=4.3",
  "piexif>=1.1.3",
  "jinja2>=3.1",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-xdist>=3.5"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Step 3 — Write `.gitignore`.**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
index.db
index.db-journal
logs/*.log
logs/*.jsonl
site/years/
site/photo/
site/search-*.json
site/duplicates.html
# keep site/index.html, site/assets/, and hand-written templates
```

**Step 4 — Set up venv and install deps.**

Run:
```bash
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/Photography && \
python3 -m venv .venv && \
./.venv/bin/pip install -e '.[dev]' 2>&1 | tail -5
```

Expected: "Successfully installed ..." for Pillow, pillow-heif, imagehash, piexif, jinja2, pytest, pytest-xdist.

**Step 5 — Verify CLI deps (exiftool, ffmpeg).**

Run:
```bash
which exiftool ffmpeg 2>&1; exiftool -ver 2>&1; ffmpeg -version 2>&1 | head -1
```

Expected: both present. If either missing, install via `brew install exiftool ffmpeg` before proceeding.

**Step 6 — Stage files (no commit yet).**

Run:
```bash
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode && \
git add Photography/pyproject.toml Photography/.gitignore
```

## Task 2: SQLite schema + smoke test

**Files:**
- Modify: `Photography/photo_index/db.py`
- Modify: `Photography/tests/test_db.py` (create)

**Step 1 — Write the failing test.**

`Photography/tests/test_db.py`:
```python
from pathlib import Path
from photo_index.db import open_db, SCHEMA_VERSION

def test_open_db_creates_schema(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    assert "files" in tables
    assert "dup_groups" in tables
    assert "schema_meta" in tables
    version = conn.execute("SELECT version FROM schema_meta").fetchone()[0]
    assert version == SCHEMA_VERSION

def test_open_db_idempotent(tmp_path: Path):
    db_path = tmp_path / "test.db"
    open_db(db_path).close()
    # second open must not fail
    conn = open_db(db_path)
    assert conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0
```

**Step 2 — Run test, expect failure.**

Run:
```bash
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/Photography && \
./.venv/bin/pytest tests/test_db.py -v 2>&1 | tail -15
```

Expected: `ModuleNotFoundError: No module named 'photo_index.db'`.

**Step 3 — Implement `db.py`.**

`Photography/photo_index/db.py`:
```python
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
  version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
  id              INTEGER PRIMARY KEY,
  path            TEXT NOT NULL UNIQUE,
  year            INTEGER,
  event_folder    TEXT,
  filename        TEXT,
  ext             TEXT,
  kind            TEXT,
  bytes           INTEGER,
  mtime           REAL,
  sha1            TEXT,
  phash           TEXT,
  width           INTEGER,
  height          INTEGER,
  exif_taken_at   TEXT,
  exif_camera     TEXT,
  exif_gps_lat    REAL,
  exif_gps_lon    REAL,
  thumb_rel       TEXT,
  indexed_at      REAL,
  deleted_at      REAL,
  error           TEXT
);

CREATE INDEX IF NOT EXISTS idx_files_year_event ON files(year, event_folder);
CREATE INDEX IF NOT EXISTS idx_files_sha1 ON files(sha1);
CREATE INDEX IF NOT EXISTS idx_files_phash ON files(phash);
CREATE INDEX IF NOT EXISTS idx_files_taken ON files(exif_taken_at);

CREATE TABLE IF NOT EXISTS dup_groups (
  id          INTEGER PRIMARY KEY,
  kind        TEXT,
  member_ids  TEXT,
  reviewed    INTEGER DEFAULT 0,
  decision    TEXT
);
"""


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None)  # autocommit; we manage txns
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    row = conn.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_meta(version) VALUES (?)", (SCHEMA_VERSION,))
    elif row[0] != SCHEMA_VERSION:
        raise RuntimeError(f"DB schema v{row[0]} != expected v{SCHEMA_VERSION}")
    return conn
```

**Step 4 — Run test, expect pass.**

Run:
```bash
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/Photography && \
./.venv/bin/pytest tests/test_db.py -v 2>&1 | tail -10
```

Expected: `2 passed`.

**Step 5 — Stage.**

```bash
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode && \
git add Photography/photo_index/db.py Photography/tests/test_db.py Photography/photo_index/__init__.py Photography/tests/__init__.py
```

## Task 3: File walker

**Files:**
- Create: `Photography/photo_index/walker.py`
- Create: `Photography/tests/test_walker.py`
- Create: `Photography/tests/fixtures/sample_tree/` (with small JPG + non-image files)

**Step 1 — Create test fixtures.**

Run:
```bash
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/Photography/tests/fixtures && \
mkdir -p sample_tree/2024/20240101-test/nested && \
./.venv/bin/python -c "
from PIL import Image
for p in ['sample_tree/2024/20240101-test/a.jpg','sample_tree/2024/20240101-test/b.JPG','sample_tree/2024/20240101-test/nested/c.heic']:
    Image.new('RGB',(8,8),'red').save(p.replace('.heic','.jpg'))
import os, shutil
shutil.copy('sample_tree/2024/20240101-test/a.jpg','sample_tree/2024/20240101-test/nested/c.heic')
open('sample_tree/2024/20240101-test/note.txt','w').write('ignore me')
open('sample_tree/2024/20240101-test/.DS_Store','w').write('ignore me')
os.makedirs('sample_tree/2024/#recycle', exist_ok=True)
open('sample_tree/2024/#recycle/ignored.jpg','w').close()
"
```

**Step 2 — Write the failing test.**

`Photography/tests/test_walker.py`:
```python
from pathlib import Path
from photo_index.walker import walk_year_folder, FileRecord

FIXTURE = Path(__file__).parent / "fixtures" / "sample_tree"

def test_walker_finds_images_ignores_junk():
    records = list(walk_year_folder(FIXTURE / "2024"))
    paths = {r.path.name for r in records}
    assert "a.jpg" in paths
    assert "b.JPG" in paths
    assert "c.heic" in paths
    assert "note.txt" not in paths
    assert ".DS_Store" not in paths
    assert "ignored.jpg" not in paths  # inside #recycle

def test_walker_extracts_year_and_event():
    records = list(walk_year_folder(FIXTURE / "2024"))
    r = next(r for r in records if r.path.name == "a.jpg")
    assert r.year == 2024
    assert r.event_folder == "20240101-test"
    assert r.kind == "image"
    assert r.ext == "jpg"

def test_walker_classifies_kind():
    records = list(walk_year_folder(FIXTURE / "2024"))
    kinds = {r.path.name: r.kind for r in records}
    assert kinds["a.jpg"] == "image"
    assert kinds["c.heic"] == "image"
```

**Step 3 — Run, expect failure.**

```bash
./.venv/bin/pytest tests/test_walker.py -v 2>&1 | tail -10
```

Expected: import error.

**Step 4 — Implement `walker.py`.**

`Photography/photo_index/walker.py`:
```python
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

IMAGE_EXTS = {"jpg", "jpeg", "png", "heic", "heif"}
RAW_EXTS   = {"cr3", "cr2", "arw", "nef", "dng", "orf", "rw2"}
VIDEO_EXTS = {"mp4", "mov", "m4v"}
ALL_EXTS   = IMAGE_EXTS | RAW_EXTS | VIDEO_EXTS
SKIP_DIRS  = {"#recycle", ".index", "@eaDir", ".Trashes", ".Spotlight-V100"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}


@dataclass(frozen=True)
class FileRecord:
    path: Path
    year: int
    event_folder: str
    filename: str
    ext: str
    kind: str  # image | raw | video
    size: int
    mtime: float


def _classify(ext: str) -> str | None:
    e = ext.lower()
    if e in IMAGE_EXTS: return "image"
    if e in RAW_EXTS:   return "raw"
    if e in VIDEO_EXTS: return "video"
    return None


def walk_year_folder(year_dir: Path) -> Iterator[FileRecord]:
    """Yield FileRecord for every indexable file under year_dir/<event>/...

    Assumes year_dir is named YYYY (e.g. /Volumes/Pictures-Vol3/2024)."""
    try:
        year = int(year_dir.name)
    except ValueError:
        raise ValueError(f"Expected year folder name YYYY, got {year_dir.name!r}")

    for event_dir in sorted(p for p in year_dir.iterdir() if p.is_dir()):
        if event_dir.name in SKIP_DIRS:
            continue
        for p in event_dir.rglob("*"):
            if not p.is_file():
                continue
            if p.name in SKIP_NAMES or p.name.startswith("._"):
                continue
            if any(part in SKIP_DIRS for part in p.relative_to(event_dir).parts):
                continue
            ext = p.suffix.lstrip(".").lower()
            kind = _classify(ext)
            if kind is None:
                continue
            st = p.stat()
            yield FileRecord(
                path=p,
                year=year,
                event_folder=event_dir.name,
                filename=p.name,
                ext=ext,
                kind=kind,
                size=st.st_size,
                mtime=st.st_mtime,
            )
```

**Step 5 — Run, expect pass.**

```bash
./.venv/bin/pytest tests/test_walker.py -v 2>&1 | tail -10
```

Expected: `3 passed`.

**Step 6 — Stage.**

```bash
git add Photography/photo_index/walker.py Photography/tests/test_walker.py
```

## Task 4: SHA-1 hasher

**Files:**
- Create: `Photography/photo_index/hasher.py`
- Create: `Photography/tests/test_hasher.py`

**Step 1 — Test.**

`Photography/tests/test_hasher.py`:
```python
from pathlib import Path
from photo_index.hasher import sha1_of_file

def test_sha1_matches_known_value(tmp_path: Path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello world")
    # sha1("hello world") = 2aae6c35c94fcfb415dbe95f408b9ce91ee846ed
    assert sha1_of_file(p) == "2aae6c35c94fcfb415dbe95f408b9ce91ee846ed"
```

**Step 2 — Run, fail.**

```bash
./.venv/bin/pytest tests/test_hasher.py -v 2>&1 | tail -5
```

**Step 3 — Implement.**

`Photography/photo_index/hasher.py`:
```python
import hashlib
from pathlib import Path

def sha1_of_file(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with p.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def sha1_and_bytes(p: Path) -> tuple[str, bytes]:
    """Return (sha1, raw_bytes). Use when we'll also decode the file.

    Avoids a second SMB read."""
    data = p.read_bytes()
    return hashlib.sha1(data).hexdigest(), data
```

**Step 4 — Pass.**

```bash
./.venv/bin/pytest tests/test_hasher.py -v 2>&1 | tail -5
```

**Step 5 — Stage.**

```bash
git add Photography/photo_index/hasher.py Photography/tests/test_hasher.py
```

## Task 5: Thumbnail generator (JPG + PNG only for M1)

RAW and video come in M2. For M1 we prove the JPG path end-to-end.

**Files:**
- Create: `Photography/photo_index/thumbs.py`
- Create: `Photography/tests/test_thumbs.py`

**Step 1 — Test.**

`Photography/tests/test_thumbs.py`:
```python
from pathlib import Path
from PIL import Image
from photo_index.thumbs import make_thumbnail, ThumbResult

def test_thumbnail_jpg_roundtrip(tmp_path: Path):
    src = tmp_path / "big.jpg"
    Image.new("RGB", (1600, 900), "blue").save(src, "JPEG", quality=90)
    out = tmp_path / "thumb.jpg"
    res = make_thumbnail(src, out, max_edge=400)
    assert isinstance(res, ThumbResult)
    assert out.exists()
    assert res.width == 1600 and res.height == 900
    with Image.open(out) as im:
        assert max(im.size) == 400
    # phash is 16 hex chars (64-bit)
    assert len(res.phash) == 16
    assert all(c in "0123456789abcdef" for c in res.phash)

def test_thumbnail_respects_orientation(tmp_path: Path):
    # build an image with EXIF orientation=6 (rotated 90°) and verify thumb is upright
    src = tmp_path / "rot.jpg"
    im = Image.new("RGB", (200, 100), "red")
    exif_bytes = b"\x49\x49\x2a\x00\x08\x00\x00\x00\x01\x00\x12\x01\x03\x00\x01\x00\x00\x00\x06\x00\x00\x00\x00\x00\x00\x00"
    im.save(src, "JPEG", exif=exif_bytes)
    out = tmp_path / "rot_thumb.jpg"
    res = make_thumbnail(src, out, max_edge=400)
    # after orientation fix, portrait dims should swap
    assert res.width == 200 and res.height == 100
    with Image.open(out) as im2:
        w, h = im2.size
        assert h > w  # upright
```

**Step 2 — Run, fail.**

```bash
./.venv/bin/pytest tests/test_thumbs.py -v 2>&1 | tail -5
```

**Step 3 — Implement.**

`Photography/photo_index/thumbs.py`:
```python
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageOps
import imagehash
import pillow_heif

pillow_heif.register_heif_opener()


@dataclass(frozen=True)
class ThumbResult:
    width: int        # original dimensions (after orientation fix)
    height: int
    phash: str        # 16-char hex


def make_thumbnail(src: Path, out: Path, max_edge: int = 400, quality: int = 82) -> ThumbResult:
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)  # respect EXIF rotation
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        orig_w, orig_h = im.size
        phash = str(imagehash.phash(im))  # 16-hex default
        im.thumbnail((max_edge, max_edge), Image.LANCZOS)
        out.parent.mkdir(parents=True, exist_ok=True)
        im.save(out, "JPEG", quality=quality, progressive=True, optimize=True)
    return ThumbResult(width=orig_w, height=orig_h, phash=phash)
```

**Step 4 — Pass.**

```bash
./.venv/bin/pytest tests/test_thumbs.py -v 2>&1 | tail -5
```

**Step 5 — Stage.**

```bash
git add Photography/photo_index/thumbs.py Photography/tests/test_thumbs.py
```

## Task 6: EXIF extractor

**Files:**
- Create: `Photography/photo_index/exifx.py`
- Create: `Photography/tests/test_exifx.py`

**Step 1 — Test.**

`Photography/tests/test_exifx.py`:
```python
from pathlib import Path
from PIL import Image
from photo_index.exifx import extract_exif, ExifData

def test_exif_empty_is_safe(tmp_path: Path):
    p = tmp_path / "plain.jpg"
    Image.new("RGB", (10,10), "white").save(p)
    data = extract_exif(p)
    assert isinstance(data, ExifData)
    assert data.taken_at is None
    assert data.camera is None

def test_exif_parses_common_fields(tmp_path: Path):
    p = tmp_path / "with_exif.jpg"
    # minimal EXIF with DateTimeOriginal + Make + Model
    import piexif
    exif = {
        "0th": {piexif.ImageIFD.Make: b"Canon", piexif.ImageIFD.Model: b"EOS R6"},
        "Exif": {piexif.ExifIFD.DateTimeOriginal: b"2024:10:30 14:22:01"},
    }
    Image.new("RGB", (10,10), "white").save(p, exif=piexif.dump(exif))
    data = extract_exif(p)
    assert data.taken_at == "2024-10-30T14:22:01"
    assert data.camera == "Canon EOS R6"
```

**Step 2 — Run, fail.**

**Step 3 — Implement `exifx.py`:**

```python
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ExifTags
import piexif

_TAG_DATETIME_ORIGINAL = 0x9003  # ExifIFD
_TAG_MAKE  = 0x010F
_TAG_MODEL = 0x0110
_TAG_GPSINFO = 0x8825


@dataclass(frozen=True)
class ExifData:
    taken_at: str | None = None    # ISO8601
    camera: str | None = None
    gps_lat: float | None = None
    gps_lon: float | None = None


def _gps_to_decimal(ref: str, vals) -> float | None:
    try:
        d = vals[0][0] / vals[0][1]
        m = vals[1][0] / vals[1][1]
        s = vals[2][0] / vals[2][1]
        dec = d + m/60 + s/3600
        if ref in (b"S", b"W", "S", "W"):
            dec = -dec
        return dec
    except Exception:
        return None


def extract_exif(p: Path) -> ExifData:
    try:
        raw = piexif.load(str(p))
    except Exception:
        return ExifData()
    taken_at = None
    dto = raw.get("Exif", {}).get(_TAG_DATETIME_ORIGINAL)
    if dto:
        s = dto.decode("ascii", "ignore").strip("\x00 ")
        # "YYYY:MM:DD HH:MM:SS" → "YYYY-MM-DDTHH:MM:SS"
        if len(s) >= 19 and s[4] == ":" and s[7] == ":":
            taken_at = s[:4] + "-" + s[5:7] + "-" + s[8:10] + "T" + s[11:19]
    make = raw.get("0th", {}).get(_TAG_MAKE, b"").decode("ascii","ignore").strip("\x00 ")
    model = raw.get("0th", {}).get(_TAG_MODEL, b"").decode("ascii","ignore").strip("\x00 ")
    camera = (make + " " + model).strip() or None
    gps = raw.get("GPS", {}) or {}
    lat = lon = None
    if gps:
        lat_ref = gps.get(1)
        lat_val = gps.get(2)
        lon_ref = gps.get(3)
        lon_val = gps.get(4)
        if lat_val and lat_ref: lat = _gps_to_decimal(lat_ref, lat_val)
        if lon_val and lon_ref: lon = _gps_to_decimal(lon_ref, lon_val)
    return ExifData(taken_at=taken_at, camera=camera, gps_lat=lat, gps_lon=lon)
```

**Step 4 — Pass.**

**Step 5 — Stage.**

## Task 7: Config module

**Files:**
- Create: `Photography/photo_index/config.py`

No test — pure constants + path math. Review by inspection.

```python
from pathlib import Path

ROOT       = Path("/Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/Photography")
MOUNT      = Path("/Volumes/Pictures-Vol3")
DB_PATH    = ROOT / "index.db"
THUMB_ROOT = MOUNT / ".index" / "thumbs"
SITE_DIR   = ROOT / "site"
LOG_DIR    = ROOT / "logs"
STATE_PATH = ROOT / "SESSION-STATE.md"

THUMB_MAX_EDGE = 400
THUMB_QUALITY  = 82
WORKERS        = 12
COMMIT_BATCH   = 100
SMB_RETRY      = 3
SMB_RETRY_DELAY = 2.0  # seconds, exponential backoff multiplier


def thumb_path(sha1: str, year: int, event: str) -> Path:
    """.index/thumbs/<year>/<event>/<sha1[:2]>/<sha1>.jpg"""
    return THUMB_ROOT / str(year) / event / sha1[:2] / f"{sha1}.jpg"


def thumb_rel(sha1: str, year: int, event: str) -> str:
    return f"{year}/{event}/{sha1[:2]}/{sha1}.jpg"


def ensure_dirs() -> None:
    for d in [LOG_DIR, SITE_DIR, SITE_DIR/"years", SITE_DIR/"photo", SITE_DIR/"assets", THUMB_ROOT]:
        d.mkdir(parents=True, exist_ok=True)
```

**Stage.**

## Task 8: Indexer core — single-file process function

Glue together walker + hasher + thumbs + exif + DB write. Still single-threaded for M1.

**Files:**
- Create: `Photography/photo_index/indexer.py`
- Create: `Photography/tests/test_indexer.py`

**Step 1 — Test.**

`Photography/tests/test_indexer.py`:
```python
from pathlib import Path
from PIL import Image
from photo_index.db import open_db
from photo_index.walker import FileRecord
from photo_index.indexer import process_file

def _make_jpg(p: Path, color="red"):
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1200, 800), color).save(p, "JPEG", quality=90)

def test_process_file_writes_thumb_and_row(tmp_path: Path):
    src = tmp_path / "2024" / "20240101-test" / "a.jpg"
    _make_jpg(src)
    db = open_db(tmp_path / "idx.db")
    thumbs = tmp_path / "thumbs"
    rec = FileRecord(
        path=src, year=2024, event_folder="20240101-test",
        filename="a.jpg", ext="jpg", kind="image",
        size=src.stat().st_size, mtime=src.stat().st_mtime,
    )
    result = process_file(rec, db, thumbs)
    assert result.error is None
    row = db.execute("SELECT sha1, phash, width, height, thumb_rel, error FROM files WHERE path=?", (str(src),)).fetchone()
    assert row is not None
    sha1, phash, w, h, thumb_rel, err = row
    assert len(sha1) == 40
    assert len(phash) == 16
    assert w == 1200 and h == 800
    assert err is None
    assert (thumbs / thumb_rel).exists()

def test_process_file_idempotent_via_mtime(tmp_path: Path):
    src = tmp_path / "2024" / "20240101-test" / "b.jpg"
    _make_jpg(src)
    db = open_db(tmp_path / "idx.db")
    thumbs = tmp_path / "thumbs"
    rec = FileRecord(
        path=src, year=2024, event_folder="20240101-test",
        filename="b.jpg", ext="jpg", kind="image",
        size=src.stat().st_size, mtime=src.stat().st_mtime,
    )
    r1 = process_file(rec, db, thumbs)
    r2 = process_file(rec, db, thumbs)
    assert r1.skipped is False
    assert r2.skipped is True
```

**Step 2 — Run, fail.**

**Step 3 — Implement `indexer.py`:**

```python
import time
from dataclasses import dataclass
from pathlib import Path
import sqlite3

from . import config
from .walker import FileRecord
from .hasher import sha1_of_file
from .thumbs import make_thumbnail
from .exifx import extract_exif


@dataclass
class ProcessResult:
    path: Path
    skipped: bool = False
    error: str | None = None


def _row_for(db: sqlite3.Connection, path: str):
    return db.execute("SELECT mtime, sha1 FROM files WHERE path=?", (path,)).fetchone()


def process_file(rec: FileRecord, db: sqlite3.Connection, thumb_root: Path) -> ProcessResult:
    path_str = str(rec.path)
    existing = _row_for(db, path_str)
    if existing and abs(existing[0] - rec.mtime) < 1e-6:
        return ProcessResult(path=rec.path, skipped=True)

    try:
        sha1 = sha1_of_file(rec.path)
        thumb_rel = config.thumb_rel(sha1, rec.year, rec.event_folder)
        thumb_abs = thumb_root / thumb_rel
        if not thumb_abs.exists():
            thumb = make_thumbnail(rec.path, thumb_abs, max_edge=config.THUMB_MAX_EDGE,
                                   quality=config.THUMB_QUALITY)
            width, height, phash = thumb.width, thumb.height, thumb.phash
        else:
            # thumb already there (rare: other file with same sha1) — decode just for pHash + dims
            thumb = make_thumbnail(rec.path, thumb_abs, max_edge=config.THUMB_MAX_EDGE,
                                   quality=config.THUMB_QUALITY)
            width, height, phash = thumb.width, thumb.height, thumb.phash
        exif = extract_exif(rec.path)
        db.execute("""
          INSERT INTO files(path, year, event_folder, filename, ext, kind, bytes, mtime,
                            sha1, phash, width, height, exif_taken_at, exif_camera,
                            exif_gps_lat, exif_gps_lon, thumb_rel, indexed_at, error)
          VALUES (?,?,?,?,?,?,?,?, ?,?,?,?, ?,?,?,?, ?, ?, NULL)
          ON CONFLICT(path) DO UPDATE SET
            mtime=excluded.mtime, sha1=excluded.sha1, phash=excluded.phash,
            width=excluded.width, height=excluded.height,
            exif_taken_at=excluded.exif_taken_at, exif_camera=excluded.exif_camera,
            exif_gps_lat=excluded.exif_gps_lat, exif_gps_lon=excluded.exif_gps_lon,
            thumb_rel=excluded.thumb_rel, indexed_at=excluded.indexed_at, error=NULL
        """, (path_str, rec.year, rec.event_folder, rec.filename, rec.ext, rec.kind,
              rec.size, rec.mtime, sha1, phash, width, height,
              exif.taken_at, exif.camera, exif.gps_lat, exif.gps_lon,
              thumb_rel, time.time()))
        return ProcessResult(path=rec.path)
    except Exception as e:
        db.execute("""
          INSERT INTO files(path, year, event_folder, filename, ext, kind, bytes, mtime,
                            indexed_at, error)
          VALUES (?,?,?,?,?,?,?,?, ?, ?)
          ON CONFLICT(path) DO UPDATE SET
            mtime=excluded.mtime, indexed_at=excluded.indexed_at, error=excluded.error
        """, (path_str, rec.year, rec.event_folder, rec.filename, rec.ext, rec.kind,
              rec.size, rec.mtime, time.time(), f"{type(e).__name__}: {e}"))
        return ProcessResult(path=rec.path, error=f"{type(e).__name__}: {e}")
```

**Step 4 — Pass.**

**Step 5 — Stage.**

## Task 9: HTML output — minimal index + one year page

**Files:**
- Create: `Photography/photo_index/html_out.py`
- Create: `Photography/photo_index/templates/year.html`
- Create: `Photography/photo_index/templates/index.html`
- Create: `Photography/site/assets/style.css`

**Step 1 — Write CSS.**

`Photography/site/assets/style.css`:
```css
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, sans-serif;
       background: #0d0d0d; color: #e8e8e8; }
header { padding: 16px 24px; border-bottom: 1px solid #222; display: flex;
         align-items: center; gap: 16px; position: sticky; top: 0;
         background: #0d0d0d; z-index: 10; }
header h1 { margin: 0; font-size: 18px; font-weight: 600; }
a { color: #8ab4ff; text-decoration: none; }
a:hover { text-decoration: underline; }
.year-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
             gap: 16px; padding: 24px; }
.year-tile { aspect-ratio: 4/3; background: #1a1a1a; border-radius: 8px;
             overflow: hidden; position: relative; }
.year-tile img { width: 100%; height: 100%; object-fit: cover; display: block; }
.year-tile .label { position: absolute; bottom: 0; left: 0; right: 0;
                    padding: 12px; background: linear-gradient(transparent, rgba(0,0,0,.85));
                    font-size: 24px; font-weight: 600; }
.year-tile .count { position: absolute; top: 12px; right: 12px; font-size: 12px;
                    background: rgba(0,0,0,.6); padding: 4px 8px; border-radius: 4px; }
.event-header { padding: 24px 24px 8px; font-size: 16px; font-weight: 600;
                color: #aaa; position: sticky; top: 52px; background: #0d0d0d; }
.photo-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
              gap: 4px; padding: 0 24px; }
.photo-grid a { display: block; aspect-ratio: 1; background: #1a1a1a; overflow: hidden; }
.photo-grid img { width: 100%; height: 100%; object-fit: cover; display: block; }
.video-badge { position: absolute; top: 4px; right: 4px; background: rgba(0,0,0,.7);
               color: white; font-size: 10px; padding: 2px 6px; border-radius: 3px; }
```

**Step 2 — Write templates.**

`Photography/photo_index/templates/index.html`:
```html
<!doctype html>
<meta charset="utf-8">
<title>Photography Index</title>
<link rel="stylesheet" href="assets/style.css">
<header><h1>Photography Index</h1><span>{{ total_files }} photos</span></header>
<section class="year-grid">
  {% for y in years %}
  <a class="year-tile" href="years/{{ y.year }}.html">
    {% if y.cover_thumb %}<img src="{{ y.cover_thumb }}" loading="lazy">{% endif %}
    <div class="count">{{ y.count }}</div>
    <div class="label">{{ y.year }}</div>
  </a>
  {% endfor %}
</section>
```

`Photography/photo_index/templates/year.html`:
```html
<!doctype html>
<meta charset="utf-8">
<title>{{ year }} — Photography Index</title>
<link rel="stylesheet" href="../assets/style.css">
<header><h1><a href="../index.html">← All Years</a> / {{ year }}</h1>
        <span>{{ total }} photos</span></header>
{% for event in events %}
<h2 class="event-header">{{ event.name }} <span style="color:#666;font-weight:normal">· {{ event.count }}</span></h2>
<div class="photo-grid">
  {% for f in event.files %}
  <a href="../photo/{{ f.sha1 }}.html" style="position:relative">
    <img src="file://{{ thumb_root }}/{{ f.thumb_rel }}" loading="lazy" alt="">
    {% if f.kind == 'video' %}<span class="video-badge">▶ VIDEO</span>{% endif %}
  </a>
  {% endfor %}
</div>
{% endfor %}
```

**Step 3 — Implement `html_out.py`.**

```python
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
import sqlite3

from . import config

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
)


def generate_index(db: sqlite3.Connection) -> None:
    config.ensure_dirs()
    years_rows = db.execute("""
      SELECT year, COUNT(*) as c
      FROM files WHERE error IS NULL AND deleted_at IS NULL AND year IS NOT NULL
      GROUP BY year ORDER BY year
    """).fetchall()
    years = []
    for year, count in years_rows:
        cover = db.execute("""
          SELECT thumb_rel FROM files WHERE year=? AND thumb_rel IS NOT NULL
            AND error IS NULL AND deleted_at IS NULL
          ORDER BY RANDOM() LIMIT 1
        """, (year,)).fetchone()
        thumb = f"file://{config.THUMB_ROOT}/{cover[0]}" if cover else None
        years.append({"year": year, "count": count, "cover_thumb": thumb})
    total = db.execute("SELECT COUNT(*) FROM files WHERE error IS NULL AND deleted_at IS NULL").fetchone()[0]
    html = _env.get_template("index.html").render(years=years, total_files=total)
    (config.SITE_DIR / "index.html").write_text(html)


def generate_year(db: sqlite3.Connection, year: int) -> None:
    rows = db.execute("""
      SELECT id, sha1, thumb_rel, event_folder, kind, filename
      FROM files WHERE year=? AND error IS NULL AND deleted_at IS NULL
      ORDER BY event_folder, exif_taken_at, filename
    """, (year,)).fetchall()
    # group by event
    events_map: dict[str, list] = {}
    for r in rows:
        events_map.setdefault(r[3], []).append({
            "id": r[0], "sha1": r[1], "thumb_rel": r[2], "kind": r[4], "filename": r[5],
        })
    events = [{"name": name, "count": len(files), "files": files}
              for name, files in events_map.items()]
    html = _env.get_template("year.html").render(
        year=year, events=events, total=len(rows), thumb_root=str(config.THUMB_ROOT))
    out = config.SITE_DIR / "years" / f"{year}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
```

**Step 4 — Stage.**

## Task 10: M1 smoke run — one event folder

**Step 1 — Write the tiny CLI entry point.**

`Photography/build_index.py`:
```python
#!/usr/bin/env python
"""Photography index CLI. Intended to be invoked by Claude, not Harv directly."""
import argparse, sys, time
from pathlib import Path

from photo_index import config, db as dbmod
from photo_index.walker import walk_year_folder
from photo_index.indexer import process_file
from photo_index.html_out import generate_index, generate_year


def cmd_index(args):
    config.ensure_dirs()
    db = dbmod.open_db(config.DB_PATH)
    target = Path(args.path).resolve()
    records = list(walk_year_folder(target))
    print(f"[index] {len(records)} files under {target}")
    if args.limit:
        records = records[:args.limit]
    ok = errs = skipped = 0
    t0 = time.time()
    for i, rec in enumerate(records, 1):
        res = process_file(rec, db, config.THUMB_ROOT)
        if res.skipped: skipped += 1
        elif res.error: errs += 1
        else: ok += 1
        if i % 25 == 0 or i == len(records):
            rate = i / (time.time() - t0)
            print(f"[index] {i}/{len(records)} ({ok} ok, {skipped} skipped, {errs} err) {rate:.1f}/s")
    print(f"[index] done in {time.time()-t0:.1f}s")


def cmd_html(args):
    db = dbmod.open_db(config.DB_PATH)
    generate_index(db)
    years = [r[0] for r in db.execute("SELECT DISTINCT year FROM files WHERE error IS NULL").fetchall()]
    for y in years:
        generate_year(db, y)
    print(f"[html] wrote index + {len(years)} year pages to {config.SITE_DIR}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_idx = sub.add_parser("index")
    p_idx.add_argument("path", help="year folder, e.g. /Volumes/Pictures-Vol3/2024")
    p_idx.add_argument("--limit", type=int, help="process only N files (for smoke tests)")
    p_idx.set_defaults(fn=cmd_index)
    p_html = sub.add_parser("html")
    p_html.set_defaults(fn=cmd_html)
    args = ap.parse_args()
    args.fn(args)

if __name__ == "__main__":
    main()
```

**Step 2 — Run smoke test on one small event folder.**

Run:
```bash
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/Photography && \
./.venv/bin/python build_index.py index /Volumes/Pictures-Vol3/2023 --limit 20 2>&1 | tail -10
```

Expected: `[index] done in ...s` with some files processed, no errors.

**Step 3 — Generate HTML.**

```bash
./.venv/bin/python build_index.py html 2>&1 | tail -3
```

Expected: `[html] wrote index + 1 year pages ...`.

**Step 4 — Verify by opening `site/index.html`.**

```bash
open /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/Photography/site/index.html
```

Harv (visually): confirm thumbnails are visible, layout looks reasonable, 2023 tile links to its event page.

**Step 5 — Update SESSION-STATE.md to reflect M1 done.**

**Step 6 — Batch commit M1.**

```bash
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode && \
git add Photography/photo_index Photography/tests Photography/build_index.py \
        Photography/site/assets Photography/pyproject.toml Photography/.gitignore \
        Photography/SESSION-STATE.md Photography/docs/plans/2026-04-22-photography-index.md && \
git -c commit.gpgsign=false commit -m "feat(photo-index): M1 end-to-end on one folder

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

If the commit hits the OneDrive NFS timeout, note in SESSION-STATE.md that M1 changes are staged, retry later. Do NOT block on git.

---

# M2 — Full year 2024 (RAW + video + threading)

Add the decode paths we skipped in M1 and turn on concurrency.

## Task 11: CR3/raw thumbnail via exiftool

**Files:**
- Modify: `Photography/photo_index/thumbs.py` (add `make_thumbnail_raw`)
- Modify: `Photography/tests/test_thumbs.py` (add RAW test — requires a real CR3; we'll use an XFAIL skip if fixture missing)

Implementation sketch:
```python
import subprocess, io

def make_thumbnail_raw(src: Path, out: Path, max_edge=400, quality=82) -> ThumbResult:
    r = subprocess.run(["exiftool", "-b", "-PreviewImage", str(src)],
                       capture_output=True, timeout=30, check=True)
    if not r.stdout:
        # fallback: try JpgFromRaw then ThumbnailImage
        r = subprocess.run(["exiftool", "-b", "-JpgFromRaw", str(src)],
                           capture_output=True, timeout=30)
    if not r.stdout:
        raise RuntimeError("no embedded preview found")
    with Image.open(io.BytesIO(r.stdout)) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode != "RGB": im = im.convert("RGB")
        orig_w, orig_h = im.size
        phash = str(imagehash.phash(im))
        im.thumbnail((max_edge, max_edge), Image.LANCZOS)
        out.parent.mkdir(parents=True, exist_ok=True)
        im.save(out, "JPEG", quality=quality, progressive=True, optimize=True)
    return ThumbResult(width=orig_w, height=orig_h, phash=phash)
```

Test against a real CR3 file in `/Volumes/Pictures-Vol3/2025/061225/IMG_4709.CR3` (use `-k` on the path so we don't copy the 26 MB file locally — reference it directly from SMB).

**Commit after green test.**

## Task 12: Video thumbnail via ffmpeg

**Files:**
- Modify: `Photography/photo_index/thumbs.py` (add `make_thumbnail_video`)

```python
def make_thumbnail_video(src: Path, out: Path, max_edge=400, quality=82, frame_at="1") -> ThumbResult:
    r = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
         "-ss", frame_at, "-i", str(src), "-vframes", "1",
         "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
        capture_output=True, timeout=60, check=True)
    with Image.open(io.BytesIO(r.stdout)) as im:
        if im.mode != "RGB": im = im.convert("RGB")
        orig_w, orig_h = im.size
        phash = str(imagehash.phash(im))
        im.thumbnail((max_edge, max_edge), Image.LANCZOS)
        _overlay_play_icon(im)  # small triangle in lower-right
        out.parent.mkdir(parents=True, exist_ok=True)
        im.save(out, "JPEG", quality=quality, progressive=True, optimize=True)
    return ThumbResult(width=orig_w, height=orig_h, phash=phash)
```

Test against a `.mov` in `/Volumes/Pictures-Vol3/Drone/DJI_0018.MP4` if readable (or generate a 1-sec test MP4 via ffmpeg in conftest).

**Commit.**

## Task 13: Dispatcher in `process_file`

**Files:**
- Modify: `Photography/photo_index/indexer.py`

Switch on `rec.kind` / `rec.ext` to pick `make_thumbnail` / `make_thumbnail_raw` / `make_thumbnail_video`. EXIF extraction for raw/video: call `exiftool -j -DateTimeOriginal -Make -Model -GPSLatitude -GPSLongitude` and parse JSON (simpler than reading raw bytes).

Test: add fixtures for each kind, assert the right decode path is invoked.

**Commit.**

## Task 14: Threading — worker pool + single-writer DB thread

**Files:**
- Create: `Photography/photo_index/runner.py`
- Modify: `Photography/build_index.py` (use runner)

Design:
- `ThreadPoolExecutor(workers=12)` for decode work.
- One queue-consumer thread owns the sqlite3 connection and batches UPSERTs (commit every 100).
- Main thread: walk → enqueue → wait for completion → print progress every 100.

```python
# sketch
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue, threading

def run_indexer(records, db_path, thumb_root, workers=12):
    write_q = queue.Queue(maxsize=1000)
    stop = object()

    def writer():
        conn = dbmod.open_db(db_path)
        batch = 0
        while True:
            item = write_q.get()
            if item is stop: break
            _write_row(conn, item)
            batch += 1
            if batch % config.COMMIT_BATCH == 0:
                conn.execute("COMMIT")
                conn.execute("BEGIN")
        conn.commit()
        conn.close()

    t = threading.Thread(target=writer, daemon=True); t.start()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_process_read_only, rec, thumb_root) for rec in records]
        for f in as_completed(futures):
            row = f.result()
            write_q.put(row)
    write_q.put(stop); t.join()
```

Test on a 200-file fixture set; verify row count matches and timing is noticeably faster than serial.

**Commit.**

## Task 15: Error handling — SMB retry, clean bail, SIGINT

**Files:**
- Modify: `Photography/photo_index/indexer.py`
- Modify: `Photography/photo_index/runner.py`

- Wrap the `read_bytes` / `exiftool` / `ffmpeg` calls with a retry decorator that retries up to `SMB_RETRY` times with exponential backoff on `OSError`, `subprocess.TimeoutExpired`, `PermissionError`.
- Track consecutive SMB errors in runner; pause 60 s if > 50 in a row, test mount with `/Volumes/Pictures-Vol3/.index` stat, bail if gone.
- `signal.signal(SIGINT, ...)` — set a flag, drain write queue, commit, exit 0.

Tests:
- Inject a fake `OSError` for one file, assert retry logic kicks in and eventually records `error` row.
- Mock SIGINT, assert DB is committed before exit.

**Commit.**

## Task 16: Progress log + SESSION-STATE updater

**Files:**
- Create: `Photography/photo_index/progress.py`

`ProgressLogger` writes formatted lines to `logs/indexer.log` (rotating, 10 MB max). Also writes a rolling summary to `SESSION-STATE.md` every 1,000 files with current year/event, % done, ETA.

**Commit.**

## Task 17: M2 real run — full 2024

Run in background (likely 30–90 min):
```bash
cd /Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/Photography && \
nohup ./.venv/bin/python build_index.py index /Volumes/Pictures-Vol3/2024 > logs/2024-run.log 2>&1 &
echo "Indexer PID: $!"
```

Tail `logs/indexer.log` periodically, update SESSION-STATE.md with PID + ETA. Use `ScheduleWakeup` if we want to auto-check in 20 min.

**Completion checks:**
- `SELECT COUNT(*), COUNT(error), COUNT(DISTINCT event_folder) FROM files WHERE year=2024;` — sanity count.
- Regenerate HTML: `build_index.py html`.
- Harv opens `site/years/2024.html` and scrolls — confirm loads, thumbs are correct, no obvious misses.

**Commit M2.**

---

# M3 — All years 2013–2025 + search

## Task 18: Full-archive run

Background run across 2013–2025. Expected 3–8 h depending on SMB speed.

```bash
for y in 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2025; do
  ./.venv/bin/python build_index.py index /Volumes/Pictures-Vol3/$y
done
```

Monitor via `ScheduleWakeup` at 30-min intervals; update SESSION-STATE.md.

## Task 19: Search JSON export

**Files:**
- Modify: `Photography/photo_index/html_out.py` (`generate_search`)

Export `site/assets/search-YYYY.json`, one per year. Each row: `{id, sha1, filename, event, year, date, camera, has_gps, kind}`.

## Task 20: Search UI

**Files:**
- Create: `Photography/site/assets/search.js`
- Modify: `Photography/photo_index/templates/index.html` (search bar)
- Create: `Photography/photo_index/templates/search.html`

Simple vanilla JS: parse query, fetch applicable `search-YYYY.json` (or all if no year filter), filter rows client-side, render grid of results with thumbnails.

Filters supported: free text (matches filename + event), `year:YYYY`, `kind:video`, `kind:raw`, `has:gps`, `sha1:<prefix>`.

Test manually — try 10 different queries, verify results.

**Commit M3.**

---

# M4 — Duplicate detection

## Task 21: Exact-match dup query

**Files:**
- Create: `Photography/photo_index/dups.py`
- Create: `Photography/tests/test_dups.py`

```python
def find_exact_dups(db):
    rows = db.execute("""
      SELECT sha1, GROUP_CONCAT(id), COUNT(*)
      FROM files WHERE sha1 IS NOT NULL AND error IS NULL AND deleted_at IS NULL
      GROUP BY sha1 HAVING COUNT(*) > 1
      ORDER BY COUNT(*) DESC
    """).fetchall()
    return rows
```

Test with a fixture DB containing duplicate sha1 rows.

## Task 22: pHash similar-match

```python
def find_similar_groups(db, threshold=4):
    # pHash is 16 hex chars. Pull all, bucket by any collision at ≤threshold hamming.
    # Efficient method: binary hamming via imagehash, chunked by first 4 chars as cheap prefilter.
    ...
```

Note: naive O(n²) is 10B comparisons for 100K files — prohibitive. Use BK-tree or LSH bucketing. Keep it simple first (bucket by first 4 hex chars of pHash, only compare within buckets) — good enough for this dataset.

## Task 23: `duplicates.html` generator

Groups with keeper heuristic, sorted by space savings. Per-group buttons capture decisions into `localStorage`, with an "Export decisions" button that downloads `decisions.json`.

## Task 24: M4 review

Open `duplicates.html`, Harv reviews a few groups, clicks decisions, exports `decisions.json` to Downloads.

**Commit M4.**

---

# M5 — Deletion workflow

## Task 25: `decisions.json` loader + dry-run

**Files:**
- Create: `Photography/photo_index/apply_decisions.py`

`build_index.py apply <decisions.json> [--dry-run]`. Dry-run mode always runs first, prints full summary: `"N files, T GB total, moving to /Volumes/Pictures-Vol3/#recycle/dup-cleanup-YYYY-MM-DD/..."`.

## Task 26: Real apply — `mv` into `#recycle/`

On Harv's explicit "yes", execute `mv` per file into dated `#recycle` subfolder. Preserve original relative path inside the dated folder.

- DB: update `deleted_at = now()` for each moved row.
- Log: append `{original_path, recycle_path, sha1, bytes, timestamp}` to `logs/deletions.jsonl`.

## Task 27: Rebuild HTML post-delete

After apply, regenerate `index.html`, year pages, and `duplicates.html` so deleted files disappear from views.

**Commit M5.**

---

## Post-M5 — ongoing operations

- **Re-index** on new photos: `build_index.py index /Volumes/Pictures-Vol3/<year>`. mtime-skip makes this cheap.
- **Phase 2 scope expansion** (topical folders) — re-use same indexer with the folder path.
- **Phase 3** — library folders (`iPhone.photoslibrary`, `M1-MAC-Backup`) — point indexer at those, then re-run dup detection *across* the whole DB to surface cross-source duplicates.

## Key files reference

| Purpose | Path |
|---|---|
| Indexer CLI | `Photography/build_index.py` |
| Core modules | `Photography/photo_index/` |
| Tests | `Photography/tests/` |
| Generated site | `Photography/site/` |
| Design doc | `Photography/docs/plans/2026-04-22-photography-index-design.md` |
| This plan | `Photography/docs/plans/2026-04-22-photography-index.md` |
| Session state | `Photography/SESSION-STATE.md` |
| SQLite DB | `Photography/index.db` |
| Logs | `Photography/logs/indexer.log`, `logs/deletions.jsonl` |
| Thumbnails | `/Volumes/Pictures-Vol3/.index/thumbs/<year>/<event>/<sha1[:2]>/<sha1>.jpg` |

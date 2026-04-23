import time
from dataclasses import dataclass, field
from pathlib import Path
import sqlite3

from . import config
from .walker import FileRecord
from .hasher import sha1_of_file
from .thumbs import make_thumbnail, make_thumbnail_raw, make_thumbnail_video, ThumbResult
from .exifx import extract_exif, extract_exif_exiftool, ExifData

# Raw formats where Pillow's native opener reliably works (TIFF-based containers).
# Anything else in walker.RAW_EXTS goes through the exiftool preview-extraction path.
_NATIVE_RAW_EXTS = {"cr2", "dng"}


@dataclass
class ProcessResult:
    path: Path
    skipped: bool = False
    error: str | None = None


@dataclass
class RowPayload:
    """Everything the writer thread needs to upsert a row. Produced by workers."""
    path: str
    year: int
    event_folder: str
    filename: str
    ext: str
    kind: str
    bytes: int
    mtime: float
    sha1: str | None = None
    phash: str | None = None
    width: int | None = None
    height: int | None = None
    exif: ExifData = field(default_factory=ExifData)
    thumb_rel: str | None = None
    error: str | None = None


def _row_for(db: sqlite3.Connection, path: str):
    return db.execute("SELECT mtime, sha1 FROM files WHERE path=?", (path,)).fetchone()


def _make_thumb_for(rec: FileRecord, thumb_abs: Path) -> ThumbResult:
    if rec.kind == "video":
        return make_thumbnail_video(rec.path, thumb_abs,
                                    max_edge=config.THUMB_MAX_EDGE,
                                    quality=config.THUMB_QUALITY)
    if rec.kind == "raw" and rec.ext not in _NATIVE_RAW_EXTS:
        return make_thumbnail_raw(rec.path, thumb_abs,
                                  max_edge=config.THUMB_MAX_EDGE,
                                  quality=config.THUMB_QUALITY)
    try:
        return make_thumbnail(rec.path, thumb_abs,
                              max_edge=config.THUMB_MAX_EDGE,
                              quality=config.THUMB_QUALITY)
    except Exception:
        if rec.kind == "raw":
            return make_thumbnail_raw(rec.path, thumb_abs,
                                      max_edge=config.THUMB_MAX_EDGE,
                                      quality=config.THUMB_QUALITY)
        raise


def _extract_exif_for(rec: FileRecord) -> ExifData:
    if rec.kind == "video" or (rec.kind == "raw" and rec.ext not in _NATIVE_RAW_EXTS):
        return extract_exif_exiftool(rec.path)
    return extract_exif(rec.path)


def prepare_row(rec: FileRecord, thumb_root: Path) -> RowPayload:
    """Pure decode work — safe to run in a worker thread. No DB access."""
    base = RowPayload(
        path=str(rec.path), year=rec.year, event_folder=rec.event_folder,
        filename=rec.filename, ext=rec.ext, kind=rec.kind,
        bytes=rec.size, mtime=rec.mtime,
    )
    try:
        sha1 = sha1_of_file(rec.path)
        thumb_rel = config.thumb_rel(sha1, rec.year, rec.event_folder)
        thumb_abs = thumb_root / thumb_rel
        thumb = _make_thumb_for(rec, thumb_abs)
        exif = _extract_exif_for(rec)
        base.sha1 = sha1
        base.phash = thumb.phash
        base.width = thumb.width
        base.height = thumb.height
        base.exif = exif
        base.thumb_rel = thumb_rel
    except Exception as e:
        base.error = f"{type(e).__name__}: {e}"
    return base


def write_row(db: sqlite3.Connection, row: RowPayload) -> None:
    """Upsert a row into `files`. Caller owns txn/commit cadence."""
    now = time.time()
    if row.error is None:
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
        """, (row.path, row.year, row.event_folder, row.filename, row.ext, row.kind,
              row.bytes, row.mtime, row.sha1, row.phash, row.width, row.height,
              row.exif.taken_at, row.exif.camera, row.exif.gps_lat, row.exif.gps_lon,
              row.thumb_rel, now))
    else:
        db.execute("""
          INSERT INTO files(path, year, event_folder, filename, ext, kind, bytes, mtime,
                            indexed_at, error)
          VALUES (?,?,?,?,?,?,?,?, ?, ?)
          ON CONFLICT(path) DO UPDATE SET
            mtime=excluded.mtime, indexed_at=excluded.indexed_at, error=excluded.error
        """, (row.path, row.year, row.event_folder, row.filename, row.ext, row.kind,
              row.bytes, row.mtime, now, row.error))


def process_file(rec: FileRecord, db: sqlite3.Connection, thumb_root: Path) -> ProcessResult:
    """Single-threaded helper: skip-check → prep → write. Used by tests + simple CLI runs."""
    path_str = str(rec.path)
    existing = _row_for(db, path_str)
    if existing and abs(existing[0] - rec.mtime) < 1e-6:
        return ProcessResult(path=rec.path, skipped=True)
    row = prepare_row(rec, thumb_root)
    write_row(db, row)
    return ProcessResult(path=rec.path, error=row.error)

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

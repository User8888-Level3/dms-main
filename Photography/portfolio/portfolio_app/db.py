"""SQLite layer for the portfolio app (stdlib only — see SPEC.md § db.py).

WAL mode, `check_same_thread=False`; `connect()` returns a NEW connection each
call — server threads and the indexer each open their own. Helper functions all
take the connection as their first argument and return plain dicts.

Timestamps are ISO8601 UTC via `now_iso()`. Rows are never deleted: vanished
files get `missing=1` (share links may still reference them).
"""
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS photos(
  id INTEGER PRIMARY KEY,
  path TEXT UNIQUE NOT NULL,          -- absolute original path on /Volumes/photo (NFC)
  folder TEXT NOT NULL,               -- top-level collection name (NFC)
  filename TEXT NOT NULL,
  sha1 TEXT NOT NULL,
  ext TEXT NOT NULL,                  -- lowercase, with dot
  kind TEXT NOT NULL,                 -- 'image' | 'video'
  width INTEGER, height INTEGER,
  bytes INTEGER, mtime REAL,
  taken_at TEXT,                      -- ISO8601 or NULL (EXIF DateTimeOriginal; else mtime)
  visibility TEXT NOT NULL DEFAULT 'private',   -- 'private' | 'public'
  is_artwork INTEGER NOT NULL DEFAULT 0,
  indexed_at TEXT NOT NULL,
  missing INTEGER NOT NULL DEFAULT 0  -- file vanished on re-index
);
CREATE INDEX IF NOT EXISTS idx_photos_folder ON photos(folder);
CREATE INDEX IF NOT EXISTS idx_photos_vis ON photos(visibility);
-- NOT unique: the same content may live in several folders (Half Moon Bay and
-- Family hold identical files) and each membership is its own row with its own
-- visibility. Derivatives stay shared — they are keyed by sha1 on the NAS.
CREATE INDEX IF NOT EXISTS idx_photos_sha1 ON photos(sha1);
CREATE TABLE IF NOT EXISTS shares(
  token TEXT PRIMARY KEY,             -- secrets.token_urlsafe(16)
  photo_id INTEGER NOT NULL REFERENCES photos(id),
  created_at TEXT NOT NULL,
  expires_at TEXT,                    -- ISO8601 UTC or NULL = never
  revoked INTEGER NOT NULL DEFAULT 0,
  note TEXT
);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""

VISIBILITIES = ("public", "private")


def now_iso() -> str:
    """Current UTC time, ISO8601 to the second (the app-wide timestamp format)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    """Open a NEW connection (each server thread / the indexer opens its own)."""
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    return conn


# ---------------------------------------------------------------- photos ----

def _dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def get_photo(conn: sqlite3.Connection, photo_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
    return dict(row) if row else None


def get_photo_by_sha1(conn: sqlite3.Connection, sha1: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM photos WHERE sha1=?", (sha1,)).fetchone()
    return dict(row) if row else None


def photos_by_sha1(conn: sqlite3.Connection, sha1: str) -> list[dict[str, Any]]:
    """EVERY row carrying this content (one per folder membership).

    The media chokepoint must consider all of them: the content is public when
    ANY membership is public, and a share token is valid when it references any
    of the row ids."""
    return _dicts(conn.execute("SELECT * FROM photos WHERE sha1=?", (sha1,)).fetchall())


def public_photos(conn: sqlite3.Connection, folder: str | None = None) -> list[dict[str, Any]]:
    """Public, non-missing photos, newest first (optionally one collection)."""
    q = "SELECT * FROM photos WHERE visibility='public' AND missing=0"
    args: tuple = ()
    if folder is not None:
        q += " AND folder=?"
        args = (folder,)
    q += " ORDER BY taken_at DESC, id DESC"
    return _dicts(conn.execute(q, args).fetchall())


def all_photos(conn: sqlite3.Connection, folder: str | None = None) -> list[dict[str, Any]]:
    """Every non-missing photo — private included (admin browsing), newest first."""
    q = "SELECT * FROM photos WHERE missing=0"
    args: tuple = ()
    if folder is not None:
        q += " AND folder=?"
        args = (folder,)
    q += " ORDER BY taken_at DESC, id DESC"
    return _dicts(conn.execute(q, args).fetchall())


def photo_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM photos WHERE missing=0").fetchone()[0]


def all_folders(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """[{folder, total, public, artwork, cover_sha1}] for every non-missing folder.

    cover = newest public photo in the folder, else newest photo."""
    rows = conn.execute("""
        SELECT folder,
               COUNT(*)                 AS total,
               SUM(visibility='public') AS public,
               SUM(is_artwork)          AS artwork
        FROM photos WHERE missing=0
        GROUP BY folder
        ORDER BY folder COLLATE NOCASE
    """).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        cover = conn.execute("""
            SELECT sha1 FROM photos
            WHERE folder=? AND missing=0 AND visibility='public'
            ORDER BY taken_at DESC, id DESC LIMIT 1
        """, (r["folder"],)).fetchone()
        if cover is None:
            cover = conn.execute("""
                SELECT sha1 FROM photos WHERE folder=? AND missing=0
                ORDER BY taken_at DESC, id DESC LIMIT 1
            """, (r["folder"],)).fetchone()
        out.append({"folder": r["folder"], "total": r["total"], "public": r["public"],
                    "artwork": r["artwork"], "cover_sha1": cover["sha1"] if cover else None})
    return out


def set_visibility(conn: sqlite3.Connection, vis: str,
                   ids: list[int] | None = None, folder: str | None = None) -> int:
    """Set visibility for a list of photo ids OR a whole folder. Returns rows changed."""
    if vis not in VISIBILITIES:
        raise ValueError(f"bad visibility {vis!r}")
    if (ids is None) == (folder is None):
        raise ValueError("pass exactly one of ids= or folder=")
    if ids is not None:
        ids = [int(i) for i in ids]
        ph = ",".join("?" * len(ids))
        cur = conn.execute(
            f"UPDATE photos SET visibility=? WHERE id IN ({ph}) AND visibility<>?",
            (vis, *ids, vis))
    else:
        cur = conn.execute(
            "UPDATE photos SET visibility=? WHERE folder=? AND visibility<>?",
            (vis, folder, vis))
    conn.commit()
    return cur.rowcount


def set_artwork(conn: sqlite3.Connection, ids: list[int], flag: bool) -> int:
    """Mark/unmark photos as artwork. Returns rows changed."""
    if not ids:
        return 0
    val = 1 if flag else 0
    ids = [int(i) for i in ids]
    ph = ",".join("?" * len(ids))
    cur = conn.execute(
        f"UPDATE photos SET is_artwork=? WHERE id IN ({ph}) AND is_artwork<>?",
        (val, *ids, val))
    conn.commit()
    return cur.rowcount


# ---------------------------------------------------------------- shares ----

def create_share(conn: sqlite3.Connection, photo_id: int,
                 expires_at: str | None = None, note: str | None = None) -> dict[str, Any]:
    """Mint a share token for one photo. `expires_at` = ISO8601 UTC or None = never."""
    token = secrets.token_urlsafe(16)
    row = {"token": token, "photo_id": int(photo_id), "created_at": now_iso(),
           "expires_at": expires_at, "revoked": 0, "note": note}
    conn.execute("""
        INSERT INTO shares(token, photo_id, created_at, expires_at, revoked, note)
        VALUES(:token, :photo_id, :created_at, :expires_at, :revoked, :note)
    """, row)
    conn.commit()
    return row


def get_share(conn: sqlite3.Connection, token: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM shares WHERE token=?", (token,)).fetchone()
    return dict(row) if row else None


def revoke_share(conn: sqlite3.Connection, token: str) -> bool:
    cur = conn.execute("UPDATE shares SET revoked=1 WHERE token=?", (token,))
    conn.commit()
    return cur.rowcount > 0


def list_shares(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """All shares (newest first), joined with photo thumb info."""
    return _dicts(conn.execute("""
        SELECT s.token, s.photo_id, s.created_at, s.expires_at, s.revoked, s.note,
               p.sha1, p.filename, p.kind
        FROM shares s JOIN photos p ON p.id = s.photo_id
        ORDER BY s.created_at DESC
    """).fetchall())


def share_valid(row: Mapping[str, Any] | None) -> bool:
    """True when the share is not revoked and not expired (NULL expiry = never)."""
    if row is None or row["revoked"]:
        return False
    exp = row["expires_at"]
    if not exp:
        return True
    try:
        dt = datetime.fromisoformat(exp)
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt > datetime.now(timezone.utc)


def expiry_from_choice(choice: str) -> str | None:
    """Map an admin expiry choice to an ISO8601 UTC timestamp (or None = never).

    '24h' | '7d' | '30d' | 'never' | 'YYYY-MM-DD' (custom date = end of that day UTC).
    Raises ValueError on anything else."""
    spans = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
    if choice == "never":
        return None
    if choice in spans:
        dt = datetime.now(timezone.utc) + spans[choice]
        return dt.isoformat(timespec="seconds")
    day = datetime.strptime(choice, "%Y-%m-%d")  # ValueError if malformed
    dt = day.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    return dt.isoformat(timespec="seconds")


# ------------------------------------------------------------------ meta ----

def meta_get(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def meta_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("""
        INSERT INTO meta(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
    """, (key, value))
    conn.commit()

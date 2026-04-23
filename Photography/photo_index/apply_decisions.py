"""Apply `decisions.json` — move files to #recycle, update DB, append audit log.

**Never** `rm`. Every file marked for deletion is moved to:

    {MOUNT}/#recycle/dup-cleanup-{YYYY-MM-DD}/{year}/{event}/{filename}

with a counter suffix added if a collision occurs (common when multiple dupes
share a basename — e.g. five IMG_1234.jpg copies across five event folders).

An append-only JSONL log at `logs/deletions.jsonl` records every move. If a
step fails mid-run the log tells us exactly where it stopped so we can resume.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config


RECYCLE_PREFIX = "dup-cleanup"
AUDIT_LOG_FILENAME = "deletions.jsonl"


@dataclass
class ApplyResult:
    moved: int
    skipped: int
    errors: int
    bytes_reclaimed: int
    recycle_root: Path | None
    dry_run: bool


def _recycle_root(run_date: str | None = None) -> Path:
    day = run_date or datetime.now().strftime("%Y-%m-%d")
    return config.MOUNT / "#recycle" / f"{RECYCLE_PREFIX}-{day}"


def _target_path(recycle_root: Path, original: Path, rec: dict) -> Path:
    """Preserve year/event structure under the recycle root so moves are reversible."""
    year = rec.get("year")
    event = rec.get("event_folder") or "unknown"
    base = recycle_root / str(year) / event / original.name
    if not base.exists():
        return base
    stem, suffix = original.stem, original.suffix
    for i in range(1, 1000):
        candidate = base.parent / f"{stem}__dup{i}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"too many filename collisions at {base.parent}")


def _load_file_info(db: sqlite3.Connection, file_id: int) -> dict | None:
    row = db.execute(
        "SELECT id, path, filename, year, event_folder, bytes, sha1, deleted_at "
        "FROM files WHERE id=?",
        (file_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0], "path": row[1], "filename": row[2], "year": row[3],
        "event_folder": row[4], "bytes": row[5] or 0, "sha1": row[6],
        "deleted_at": row[7],
    }


def apply_decisions(
    decisions_payload: dict[str, Any],
    db_path: Path = config.DB_PATH,
    *,
    dry_run: bool = True,
    run_date: str | None = None,
    log_path: Path | None = None,
) -> ApplyResult:
    decisions = decisions_payload.get("decisions") or {}
    recycle_root = _recycle_root(run_date)
    log_path = log_path or (config.LOG_DIR / AUDIT_LOG_FILENAME)

    moved = skipped = errors = 0
    bytes_reclaimed = 0

    if dry_run:
        db = sqlite3.connect(db_path)
    else:
        db = sqlite3.connect(db_path, isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_fh = log_path.open("a", buffering=1)
        recycle_root.mkdir(parents=True, exist_ok=True)

    try:
        for gid, dec in decisions.items():
            if dec.get("action") != "apply":
                continue
            for file_id in dec.get("delete_ids", []):
                info = _load_file_info(db, file_id)
                if info is None:
                    skipped += 1
                    continue
                if info.get("deleted_at") is not None:
                    skipped += 1
                    continue
                src = Path(info["path"])
                if not src.exists():
                    errors += 1
                    if not dry_run:
                        log_fh.write(json.dumps({
                            "ts": time.time(), "ok": False,
                            "reason": "source missing", "file_id": file_id,
                            "path": info["path"],
                        }) + "\n")
                    continue
                dst = _target_path(recycle_root, src, info)
                if dry_run:
                    moved += 1
                    bytes_reclaimed += info["bytes"]
                    continue
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dst))
                except Exception as e:
                    errors += 1
                    log_fh.write(json.dumps({
                        "ts": time.time(), "ok": False,
                        "reason": f"{type(e).__name__}: {e}",
                        "file_id": file_id, "src": str(src), "dst": str(dst),
                    }) + "\n")
                    continue
                db.execute("UPDATE files SET deleted_at=? WHERE id=?",
                           (time.time(), file_id))
                log_fh.write(json.dumps({
                    "ts": time.time(), "ok": True,
                    "gid": gid, "kind": dec.get("kind"),
                    "file_id": file_id, "sha1": info["sha1"],
                    "src": str(src), "dst": str(dst),
                    "bytes": info["bytes"],
                }) + "\n")
                moved += 1
                bytes_reclaimed += info["bytes"]
    finally:
        if not dry_run:
            log_fh.close()
        db.close()

    return ApplyResult(
        moved=moved, skipped=skipped, errors=errors,
        bytes_reclaimed=bytes_reclaimed,
        recycle_root=recycle_root if not dry_run else None,
        dry_run=dry_run,
    )

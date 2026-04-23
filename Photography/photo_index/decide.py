"""Programmatic decision generator for dup groups.

Replaces (for bulk cases) the per-group manual click-through in duplicates.html.
Emits a decisions blob with the same schema the HTML exports so M5 can apply it.

Heuristics:

Exact dups (SHA-1 match — byte-identical):
  Auto-apply. Keeper picked by, in priority order:
    1. NOT in a "backup / copy / tmp" path segment
    2. Shortest path depth (closer to organized root)
    3. Oldest mtime (likely the original import)
    4. Smallest id (stable tiebreak)

Similar dups (pHash Hamming ≤ threshold, union-find clustered):
  Auto-apply ONLY for small clusters (default ≤ 2 members) — those are almost
  always resize/recompression pairs. Bigger clusters (bursts, edit variants)
  are SKIPPED and left for Harv to review visually.

  Keeper for a 2-member similar group: largest bytes (highest quality).
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pathlib import Path

from .dups import find_exact_dups, find_similar_groups


_BACKUP_PAT = re.compile(
    r"(?:^|[/\s._-])(?:"
    r"copy|Copy|COPY|"
    r"copy\s*\d+|Copy\s*\d+|"
    r"backup|Backup|BACKUP|bak|BAK|"
    r"old|Old|OLD|"
    r"tmp|TMP|temp|Temp|TEMP|"
    r"dupes?|Dupes?|DUPES?|"
    r"duplicate|Duplicate|DUPLICATE|"
    r"imported|Imported|IMPORTED"
    r")(?:$|[/\s._-])"
)


def _looks_like_backup(path: str) -> bool:
    return bool(_BACKUP_PAT.search(path))


_RAW_EXTS = {"cr2", "cr3", "arw", "nef", "dng", "orf", "rw2"}
_JPG_EXTS = {"jpg", "jpeg"}


def _is_raw_jpg_pair(files: list[dict]) -> bool:
    """True iff files are exactly one raw + one JPG/JPEG with the same stem,
    both in the same parent directory. This is the canonical "camera saved
    both formats" situation — safe to drop the JPG."""
    if len(files) != 2:
        return False
    p0, p1 = Path(files[0]["path"]), Path(files[1]["path"])
    if p0.parent != p1.parent:
        return False
    if p0.stem.lower() != p1.stem.lower():
        return False
    exts = {p0.suffix.lstrip(".").lower(), p1.suffix.lstrip(".").lower()}
    return bool(exts & _RAW_EXTS) and bool(exts & _JPG_EXTS)


import re as _re
_NUMERIC_SUFFIX = _re.compile(r"-\d+$")


def _has_numeric_suffix(path: str) -> bool:
    """Detects filenames like IMG_7899-1.CR2, IMG_2001-3.jpg — likely a copy."""
    stem = Path(path).stem
    return bool(_NUMERIC_SUFFIX.search(stem))


def _pick_keeper_exact(files: list[dict]) -> int:
    def sort_key(f: dict) -> tuple:
        path = f["path"]
        return (
            1 if _looks_like_backup(path) else 0,   # non-backup first
            1 if _has_numeric_suffix(path) else 0,  # unsuffixed name first
            path.count("/"),                         # shallower first
            f["mtime"] or 0.0,                       # oldest first
            f["id"],                                 # deterministic
        )
    return sorted(files, key=sort_key)[0]["id"]


def _pick_keeper_similar(files: list[dict]) -> int:
    def sort_key(f: dict) -> tuple:
        path = f["path"]
        return (
            1 if _looks_like_backup(path) else 0,
            -int(f["bytes"] or 0),                   # largest first
            -(f["mtime"] or 0.0),                    # newest first (edited version)
            f["id"],
        )
    return sorted(files, key=sort_key)[0]["id"]


@dataclass
class DecisionSummary:
    total_groups: int
    applied_exact: int
    applied_similar: int
    skipped_similar_large: int
    files_to_delete: int
    bytes_to_reclaim: int


def _fetch_files_by_ids(db: sqlite3.Connection, ids: list[int]) -> list[dict]:
    placeholders = ",".join("?" * len(ids))
    rows = db.execute(
        f"SELECT id, path, bytes, mtime, sha1, filename "
        f"FROM files WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
    return [
        {"id": r[0], "path": r[1], "bytes": r[2], "mtime": r[3],
         "sha1": r[4], "filename": r[5]}
        for r in rows
    ]


def auto_decide_all(
    db: sqlite3.Connection,
    *,
    similar_threshold: int = 4,
    similar_max_cluster_size: int = 2,
) -> dict[str, Any]:
    exact_groups = find_exact_dups(db)
    similar_groups = find_similar_groups(db, threshold=similar_threshold)

    decisions: dict[str, dict] = {}
    already_decided: set[int] = set()   # file ids already covered by exact

    applied_exact = 0
    applied_similar = 0
    skipped_similar_large = 0
    files_to_delete = 0
    bytes_to_reclaim = 0

    # Exact first — authoritative.
    for g in exact_groups:
        files = _fetch_files_by_ids(db, g["ids"])
        keeper = _pick_keeper_exact(files)
        delete_ids = [f["id"] for f in files if f["id"] != keeper]
        already_decided.update(f["id"] for f in files)
        gid = f"e{g['ids'][0]}"
        decisions[gid] = {
            "action": "apply",
            "kind": "exact",
            "keeper_id": keeper,
            "delete_ids": delete_ids,
        }
        applied_exact += 1
        files_to_delete += len(delete_ids)
        bytes_to_reclaim += sum(f["bytes"] for f in files if f["id"] in delete_ids)

    # Similar — only auto-apply pairs that are *clearly* the same capture in
    # different formats (raw + jpg pair). Sequential burst shots get skipped.
    for g in similar_groups:
        ids = g["ids"]
        if any(i in already_decided for i in ids):
            continue
        if len(ids) != 2:
            skipped_similar_large += 1
            continue
        files = _fetch_files_by_ids(db, ids)
        if not _is_raw_jpg_pair(files):
            skipped_similar_large += 1
            continue
        keeper = _pick_keeper_similar(files)
        delete_ids = [f["id"] for f in files if f["id"] != keeper]
        gid = f"s{ids[0]}"
        decisions[gid] = {
            "action": "apply",
            "kind": "similar",
            "keeper_id": keeper,
            "delete_ids": delete_ids,
        }
        applied_similar += 1
        files_to_delete += len(delete_ids)
        bytes_to_reclaim += sum(f["bytes"] for f in files if f["id"] in delete_ids)

    summary = DecisionSummary(
        total_groups=len(decisions),
        applied_exact=applied_exact,
        applied_similar=applied_similar,
        skipped_similar_large=skipped_similar_large,
        files_to_delete=files_to_delete,
        bytes_to_reclaim=bytes_to_reclaim,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "heuristic": {
            "exact": "not-backup path, shortest path, oldest mtime",
            "similar_max_cluster_size": similar_max_cluster_size,
            "similar_cross_year": "skipped (possible pHash false positive)",
        },
        "count": len(decisions),
        "decisions": decisions,
        "summary": {
            "total_groups": summary.total_groups,
            "applied_exact": summary.applied_exact,
            "applied_similar": summary.applied_similar,
            "skipped_similar_large": summary.skipped_similar_large,
            "files_to_delete": summary.files_to_delete,
            "bytes_to_reclaim": summary.bytes_to_reclaim,
        },
    }

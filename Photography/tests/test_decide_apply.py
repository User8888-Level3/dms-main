import json
import shutil
from pathlib import Path
from PIL import Image

from photo_index.db import open_db
from photo_index.walker import FileRecord
from photo_index.indexer import process_file
from photo_index.decide import auto_decide_all, _pick_keeper_exact, _looks_like_backup
from photo_index.apply_decisions import apply_decisions, _recycle_root
from photo_index import config


def _rec(p: Path, year: int, event: str) -> FileRecord:
    return FileRecord(
        path=p, year=year, event_folder=event,
        filename=p.name, ext=p.suffix.lstrip("."), kind="image",
        size=p.stat().st_size, mtime=p.stat().st_mtime,
    )


def test_looks_like_backup_detects_common_patterns():
    assert _looks_like_backup("/foo/bar/Copy/img.jpg")
    assert _looks_like_backup("/foo/backup/img.jpg")
    assert _looks_like_backup("/foo/tmp/img.jpg")
    assert _looks_like_backup("/foo/img.jpg.bak")
    assert _looks_like_backup("/foo/dupes/img.jpg")
    assert not _looks_like_backup("/foo/2024/20240101-test/img.jpg")


def test_pick_keeper_exact_prefers_non_backup_and_shallow():
    files = [
        {"id": 1, "path": "/foo/2024/a/b/c/d/e/img.jpg", "mtime": 100.0},
        {"id": 2, "path": "/foo/2024/a/img.jpg",           "mtime": 500.0},
        {"id": 3, "path": "/foo/backup/img.jpg",           "mtime": 50.0},
    ]
    # Non-backup, shallowest, even though not oldest → id 2 wins
    assert _pick_keeper_exact(files) == 2


def test_auto_decide_with_exact_dups(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "THUMB_ROOT", tmp_path / "thumbs")
    db = open_db(tmp_path / "idx.db")
    thumbs = tmp_path / "thumbs"
    # Two byte-identical files
    original = tmp_path / "2024" / "main" / "x.jpg"
    original.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (400, 300), "magenta").save(original, "JPEG")
    backup = tmp_path / "2024" / "Copy" / "x.jpg"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(original, backup)
    for p, event in [(original, "main"), (backup, "Copy")]:
        process_file(_rec(p, 2024, event), db, thumbs)

    payload = auto_decide_all(db)
    assert payload["summary"]["applied_exact"] == 1
    assert payload["summary"]["files_to_delete"] == 1
    # Keeper is the non-"Copy" path
    one_decision = next(iter(payload["decisions"].values()))
    keeper_path = db.execute(
        "SELECT path FROM files WHERE id=?", (one_decision["keeper_id"],)
    ).fetchone()[0]
    assert "Copy" not in keeper_path


def test_apply_dry_run_does_not_move_or_mutate(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "MOUNT", tmp_path / "mount")
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "THUMB_ROOT", tmp_path / "thumbs")
    (tmp_path / "mount").mkdir()
    db_path = tmp_path / "idx.db"
    db = open_db(db_path)
    thumbs = tmp_path / "thumbs"
    orig = tmp_path / "2024" / "main" / "x.jpg"
    orig.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (400, 300), "orange").save(orig, "JPEG")
    dup = tmp_path / "2024" / "Copy" / "x.jpg"
    dup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(orig, dup)
    for p, ev in [(orig, "main"), (dup, "Copy")]:
        process_file(_rec(p, 2024, ev), db, thumbs)
    payload = auto_decide_all(db)
    db.close()

    result = apply_decisions(payload, db_path=db_path, dry_run=True)
    assert result.dry_run is True
    assert result.moved == 1
    assert result.bytes_reclaimed > 0
    # Nothing actually moved
    assert orig.exists() and dup.exists()
    # DB deleted_at still null
    db2 = open_db(db_path)
    assert all(row[0] is None for row in db2.execute("SELECT deleted_at FROM files"))


def test_apply_real_moves_to_recycle_and_updates_db(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "MOUNT", tmp_path / "mount")
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "THUMB_ROOT", tmp_path / "thumbs")
    (tmp_path / "mount").mkdir()
    db_path = tmp_path / "idx.db"
    db = open_db(db_path)
    thumbs = tmp_path / "thumbs"
    orig = tmp_path / "2024" / "main" / "y.jpg"
    orig.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (400, 300), "teal").save(orig, "JPEG")
    dup = tmp_path / "2024" / "Copy" / "y.jpg"
    dup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(orig, dup)
    for p, ev in [(orig, "main"), (dup, "Copy")]:
        process_file(_rec(p, 2024, ev), db, thumbs)
    payload = auto_decide_all(db)
    db.close()

    result = apply_decisions(payload, db_path=db_path, dry_run=False, run_date="2026-04-23")
    assert result.dry_run is False
    assert result.moved == 1
    # The "Copy" one moved to recycle
    assert not dup.exists()
    assert orig.exists()
    recycle = tmp_path / "mount" / "#recycle" / "dup-cleanup-2026-04-23"
    assert recycle.exists()
    # deleted_at set for the moved file
    db2 = open_db(db_path)
    deleted = db2.execute("SELECT COUNT(*) FROM files WHERE deleted_at IS NOT NULL").fetchone()[0]
    assert deleted == 1
    # Audit log appended
    log = tmp_path / "logs" / "deletions.jsonl"
    assert log.exists()
    entries = [json.loads(l) for l in log.read_text().strip().splitlines()]
    assert len(entries) == 1
    assert entries[0]["ok"] is True
    assert entries[0]["kind"] == "exact"

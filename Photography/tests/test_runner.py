import threading
from pathlib import Path
from PIL import Image
from photo_index.db import open_db
from photo_index.walker import FileRecord
from photo_index.runner import run_indexer, RunStats


def _make_records(root: Path, n: int, year: int = 2024, event: str = "20240101-test") -> list[FileRecord]:
    event_dir = root / str(year) / event
    event_dir.mkdir(parents=True, exist_ok=True)
    recs = []
    for i in range(n):
        p = event_dir / f"img_{i:02d}.jpg"
        Image.new("RGB", (600, 400), (i * 20 % 256, 100, 200)).save(p, "JPEG", quality=85)
        st = p.stat()
        recs.append(FileRecord(
            path=p, year=year, event_folder=event,
            filename=p.name, ext="jpg", kind="image",
            size=st.st_size, mtime=st.st_mtime,
        ))
    return recs


def test_runner_indexes_many_files(tmp_path: Path):
    recs = _make_records(tmp_path / "src", n=8)
    db_path = tmp_path / "idx.db"
    thumbs = tmp_path / "thumbs"
    stats = run_indexer(recs, db_path, thumbs, workers=4)
    assert isinstance(stats, RunStats)
    assert stats.ok == 8
    assert stats.errors == 0
    assert stats.skipped == 0
    db = open_db(db_path)
    assert db.execute("SELECT COUNT(*) FROM files WHERE error IS NULL").fetchone()[0] == 8
    # every thumb exists
    for (thumb_rel,) in db.execute("SELECT thumb_rel FROM files").fetchall():
        assert (thumbs / thumb_rel).exists()


def test_runner_skips_unchanged_on_rerun(tmp_path: Path):
    recs = _make_records(tmp_path / "src", n=3)
    db_path = tmp_path / "idx.db"
    thumbs = tmp_path / "thumbs"
    first = run_indexer(recs, db_path, thumbs, workers=2)
    assert first.ok == 3 and first.skipped == 0
    second = run_indexer(recs, db_path, thumbs, workers=2)
    assert second.ok == 0
    assert second.skipped == 3


def test_runner_records_errors_without_aborting(tmp_path: Path):
    recs = _make_records(tmp_path / "src", n=3)
    # Corrupt one file so decode fails
    recs[1].path.write_bytes(b"not a real jpeg")
    db_path = tmp_path / "idx.db"
    thumbs = tmp_path / "thumbs"
    stats = run_indexer(recs, db_path, thumbs, workers=3)
    assert stats.ok == 2
    assert stats.errors == 1
    db = open_db(db_path)
    err_row = db.execute("SELECT path, error FROM files WHERE error IS NOT NULL").fetchone()
    assert err_row is not None
    assert err_row[0] == str(recs[1].path)


def test_runner_honors_stop_event(tmp_path: Path):
    recs = _make_records(tmp_path / "src", n=30)
    db_path = tmp_path / "idx.db"
    thumbs = tmp_path / "thumbs"
    stop = threading.Event()
    stop.set()  # signal before start — runner should do minimal/no work
    stats = run_indexer(recs, db_path, thumbs, workers=2, stop_event=stop)
    # Some workers already have futures in flight; processed count should be well under total
    db = open_db(db_path)
    written = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    assert written < len(recs)
    assert stats.total == len(recs)

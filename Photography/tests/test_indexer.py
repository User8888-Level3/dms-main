import subprocess
from pathlib import Path
import pytest
from PIL import Image
from photo_index.db import open_db
from photo_index.walker import FileRecord
from photo_index.indexer import process_file

CR3_FIXTURE = Path("/Volumes/Pictures-Vol3/2025/061225/IMG_4709.CR3")


def _make_jpg(p: Path, color="red"):
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1200, 800), color).save(p, "JPEG", quality=90)


def _make_mp4(p: Path, seconds: int = 2, size: str = "640x480") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", f"color=c=blue:s={size}:d={seconds}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(seconds),
         str(p)],
        check=True, capture_output=True, timeout=30,
    )


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
    row = db.execute(
        "SELECT sha1, phash, width, height, thumb_rel, error FROM files WHERE path=?",
        (str(src),),
    ).fetchone()
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


def test_process_file_dispatches_video(tmp_path: Path):
    src = tmp_path / "2024" / "20240101-test" / "clip.mp4"
    _make_mp4(src, seconds=2, size="640x480")
    db = open_db(tmp_path / "idx.db")
    thumbs = tmp_path / "thumbs"
    rec = FileRecord(
        path=src, year=2024, event_folder="20240101-test",
        filename="clip.mp4", ext="mp4", kind="video",
        size=src.stat().st_size, mtime=src.stat().st_mtime,
    )
    result = process_file(rec, db, thumbs)
    assert result.error is None
    row = db.execute(
        "SELECT sha1, phash, width, height, thumb_rel, error FROM files WHERE path=?",
        (str(src),),
    ).fetchone()
    assert row is not None
    sha1, phash, w, h, thumb_rel, err = row
    assert len(sha1) == 40
    assert len(phash) == 16
    assert w == 640 and h == 480
    assert err is None
    assert (thumbs / thumb_rel).exists()


@pytest.mark.skipif(not CR3_FIXTURE.exists(), reason="SMB CR3 fixture unavailable")
def test_process_file_dispatches_raw_cr3(tmp_path: Path):
    db = open_db(tmp_path / "idx.db")
    thumbs = tmp_path / "thumbs"
    st = CR3_FIXTURE.stat()
    rec = FileRecord(
        path=CR3_FIXTURE, year=2025, event_folder="061225",
        filename=CR3_FIXTURE.name, ext="cr3", kind="raw",
        size=st.st_size, mtime=st.st_mtime,
    )
    result = process_file(rec, db, thumbs)
    assert result.error is None, result.error
    row = db.execute(
        "SELECT sha1, phash, thumb_rel, exif_taken_at, exif_camera, error "
        "FROM files WHERE path=?",
        (str(CR3_FIXTURE),),
    ).fetchone()
    assert row is not None
    sha1, phash, thumb_rel, taken_at, camera, err = row
    assert err is None
    assert len(sha1) == 40
    assert len(phash) == 16
    assert (thumbs / thumb_rel).exists()
    # EXIF from exiftool should yield Canon EOS RP + 2025-06-12 date
    assert taken_at and taken_at.startswith("2025-06-12")
    assert camera and "Canon" in camera

from pathlib import Path
from unittest.mock import patch
from PIL import Image
from photo_index.db import open_db
from photo_index.walker import FileRecord
from photo_index.indexer import process_file
from photo_index import html_out, config


def test_generate_index_and_year(tmp_path: Path, monkeypatch):
    # Redirect config paths so the test doesn't touch real dirs
    site_dir = tmp_path / "site"
    thumb_root = tmp_path / "thumbs"
    monkeypatch.setattr(config, "SITE_DIR", site_dir)
    monkeypatch.setattr(config, "THUMB_ROOT", thumb_root)
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")

    # Create a small DB with two events in 2024
    db = open_db(tmp_path / "idx.db")
    for name in ("a.jpg", "b.jpg"):
        p = tmp_path / "2024" / "20240101-test" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (400, 300), "red").save(p, "JPEG")
        rec = FileRecord(path=p, year=2024, event_folder="20240101-test",
                         filename=name, ext="jpg", kind="image",
                         size=p.stat().st_size, mtime=p.stat().st_mtime)
        process_file(rec, db, thumb_root)
    for name in ("c.jpg",):
        p = tmp_path / "2024" / "20240215-other" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (400, 300), "blue").save(p, "JPEG")
        rec = FileRecord(path=p, year=2024, event_folder="20240215-other",
                         filename=name, ext="jpg", kind="image",
                         size=p.stat().st_size, mtime=p.stat().st_mtime)
        process_file(rec, db, thumb_root)

    # Generate index + year page
    html_out.generate_index(db)
    html_out.generate_year(db, 2024)

    idx = site_dir / "index.html"
    yr = site_dir / "years" / "2024.html"
    assert idx.exists()
    assert yr.exists()
    idx_html = idx.read_text()
    yr_html = yr.read_text()
    # sanity: index mentions the year and total count
    assert "2024" in idx_html
    assert "3 photos" in idx_html
    # year page groups by event and shows all 3 thumbnails
    assert "20240101-test" in yr_html
    assert "20240215-other" in yr_html
    # 3 thumbnail <img> tags present
    assert yr_html.count("<img") >= 3

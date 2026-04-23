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


def test_generate_search_json(tmp_path: Path, monkeypatch):
    import json
    site_dir = tmp_path / "site"
    thumb_root = tmp_path / "thumbs"
    monkeypatch.setattr(config, "SITE_DIR", site_dir)
    monkeypatch.setattr(config, "THUMB_ROOT", thumb_root)
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")

    db = open_db(tmp_path / "idx.db")
    # 2 files in 2023, 1 in 2024
    for year, event, name in [
        (2023, "20230501-test", "a.jpg"),
        (2023, "20230501-test", "b.jpg"),
        (2024, "20240101-other", "c.jpg"),
    ]:
        p = tmp_path / str(year) / event / name
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (400, 300), "red").save(p, "JPEG")
        rec = FileRecord(path=p, year=year, event_folder=event,
                         filename=name, ext="jpg", kind="image",
                         size=p.stat().st_size, mtime=p.stat().st_mtime)
        process_file(rec, db, thumb_root)

    manifest = html_out.generate_search_json(db)
    assert {m["year"] for m in manifest} == {2023, 2024}
    assert {m["count"] for m in manifest} == {1, 2}

    # per-year JSON
    s2023 = json.loads((site_dir / "assets" / "search-2023.json").read_text())
    s2024 = json.loads((site_dir / "assets" / "search-2024.json").read_text())
    assert len(s2023) == 2 and len(s2024) == 1
    first = s2023[0]
    assert {"id", "sha1", "f", "e", "d", "c", "g", "k", "t"} <= set(first.keys())
    assert first["k"] == "image"
    assert first["g"] is False

    # manifest
    mf = json.loads((site_dir / "assets" / "search-manifest.json").read_text())
    assert mf["thumb_root"] == "thumbs"
    assert len(mf["years"]) == 2


def test_generate_duplicates_html(tmp_path: Path, monkeypatch):
    import shutil
    site_dir = tmp_path / "site"
    thumb_root = tmp_path / "thumbs"
    monkeypatch.setattr(config, "SITE_DIR", site_dir)
    monkeypatch.setattr(config, "THUMB_ROOT", thumb_root)
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")

    db = open_db(tmp_path / "idx.db")
    # Two byte-identical files → exact dup group
    original = tmp_path / "2024" / "a" / "original.jpg"
    original.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (600, 400), "cyan").save(original, "JPEG")
    copy = tmp_path / "2024" / "b" / "copy.jpg"
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(original, copy)
    for src, event, name in [(original, "a", "original.jpg"), (copy, "b", "copy.jpg")]:
        rec = FileRecord(path=src, year=2024, event_folder=event,
                         filename=name, ext="jpg", kind="image",
                         size=src.stat().st_size, mtime=src.stat().st_mtime)
        process_file(rec, db, thumb_root)

    stats = html_out.generate_duplicates_html(db)
    assert stats["exact_groups"] == 1
    assert stats["exact_files"] == 2
    out = site_dir / "duplicates.html"
    assert out.exists()
    html = out.read_text()
    assert "EXACT" in html
    assert "original.jpg" in html and "copy.jpg" in html
    # Keeper should be marked
    assert "keeper" in html

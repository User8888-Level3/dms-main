from pathlib import Path
from photo_index.walker import walk_year_folder, FileRecord

FIXTURE = Path(__file__).parent / "fixtures" / "sample_tree"

def test_walker_finds_images_ignores_junk():
    records = list(walk_year_folder(FIXTURE / "2024"))
    paths = {r.path.name for r in records}
    assert "a.jpg" in paths
    assert "b.JPG" in paths
    assert "c.heic" in paths
    assert "note.txt" not in paths
    assert ".DS_Store" not in paths
    assert "ignored.jpg" not in paths  # inside #recycle

def test_walker_extracts_year_and_event():
    records = list(walk_year_folder(FIXTURE / "2024"))
    r = next(r for r in records if r.path.name == "a.jpg")
    assert r.year == 2024
    assert r.event_folder == "20240101-test"
    assert r.kind == "image"
    assert r.ext == "jpg"

def test_walker_classifies_kind():
    records = list(walk_year_folder(FIXTURE / "2024"))
    kinds = {r.path.name: r.kind for r in records}
    assert kinds["a.jpg"] == "image"
    assert kinds["c.heic"] == "image"

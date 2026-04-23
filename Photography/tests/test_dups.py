import random
from pathlib import Path
from PIL import Image, ImageDraw
from photo_index.db import open_db
from photo_index.walker import FileRecord
from photo_index.indexer import process_file
from photo_index.dups import find_exact_dups, find_similar_groups


def _patterned_image(size=(200, 200), seed=1) -> Image.Image:
    """Deterministic image with enough visual variation that pHash is meaningful.

    Solid-color PIL images produce zero AC DCT coefficients → all images get the
    same pHash → tests can't distinguish them. Drawing random shapes fixes this.
    """
    im = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(im)
    r = random.Random(seed)
    for _ in range(30):
        x1, y1 = r.randint(0, size[0]), r.randint(0, size[1])
        x2, y2 = r.randint(0, size[0]), r.randint(0, size[1])
        color = (r.randint(0, 255), r.randint(0, 255), r.randint(0, 255))
        draw.line((x1, y1, x2, y2), fill=color, width=3)
    return im


def _ingest(tmp_path: Path, name: str, year: int, event: str,
            color="red", size=(400, 300), pattern_seed: int | None = None):
    p = tmp_path / str(year) / event / name
    p.parent.mkdir(parents=True, exist_ok=True)
    if pattern_seed is not None:
        _patterned_image(size, pattern_seed).save(p, "JPEG", quality=90)
    else:
        Image.new("RGB", size, color).save(p, "JPEG", quality=90)
    return FileRecord(
        path=p, year=year, event_folder=event,
        filename=name, ext="jpg", kind="image",
        size=p.stat().st_size, mtime=p.stat().st_mtime,
    )


def test_find_exact_dups_groups_identical_sha1(tmp_path: Path):
    db = open_db(tmp_path / "idx.db")
    thumbs = tmp_path / "thumbs"
    # Two identical content JPEGs (same pixels, same file bytes)
    import shutil
    rec_a = _ingest(tmp_path, "a.jpg", 2024, "evt1", color="blue")
    # Physically copy file to get byte-identical content with different path
    copy_path = tmp_path / "2024" / "evt2" / "copy.jpg"
    copy_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(rec_a.path, copy_path)
    rec_copy = FileRecord(
        path=copy_path, year=2024, event_folder="evt2",
        filename="copy.jpg", ext="jpg", kind="image",
        size=copy_path.stat().st_size, mtime=copy_path.stat().st_mtime,
    )
    # Unique file
    rec_b = _ingest(tmp_path, "b.jpg", 2024, "evt1", color="green")
    for rec in (rec_a, rec_copy, rec_b):
        process_file(rec, db, thumbs)

    dups = find_exact_dups(db)
    assert len(dups) == 1
    g = dups[0]
    assert g["count"] == 2
    assert len(g["ids"]) == 2
    assert g["total_bytes"] > 0


def test_find_exact_dups_empty_when_no_dups(tmp_path: Path):
    db = open_db(tmp_path / "idx.db")
    thumbs = tmp_path / "thumbs"
    for c, name in [("red", "a.jpg"), ("green", "b.jpg"), ("blue", "c.jpg")]:
        rec = _ingest(tmp_path, name, 2024, "evt", color=c)
        process_file(rec, db, thumbs)
    assert find_exact_dups(db) == []


def test_find_similar_groups_clusters_near_phash(tmp_path: Path):
    db = open_db(tmp_path / "idx.db")
    thumbs = tmp_path / "thumbs"
    # Same pattern saved as two distinct files (different bytes, same visual).
    rec_a = _ingest(tmp_path, "a.jpg", 2024, "evt1", pattern_seed=42)
    rec_b = _ingest(tmp_path, "b.jpg", 2024, "evt2", pattern_seed=42)
    # Totally different pattern — pHash should diverge.
    rec_c = _ingest(tmp_path, "c.jpg", 2024, "evt1", pattern_seed=999)
    for rec in (rec_a, rec_b, rec_c):
        process_file(rec, db, thumbs)

    groups = find_similar_groups(db, threshold=4)
    # A and B cluster; C stands alone
    assert any(len(g["ids"]) >= 2 for g in groups)
    clustered = next(g for g in groups if len(g["ids"]) >= 2)
    c_id = db.execute("SELECT id FROM files WHERE filename='c.jpg'").fetchone()[0]
    assert c_id not in clustered["ids"]


def test_find_similar_groups_handles_empty_db(tmp_path: Path):
    db = open_db(tmp_path / "idx.db")
    assert find_similar_groups(db, threshold=4) == []

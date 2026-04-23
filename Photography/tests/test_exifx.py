from pathlib import Path
from PIL import Image
from photo_index.exifx import extract_exif, ExifData, _join_camera

def test_exif_empty_is_safe(tmp_path: Path):
    p = tmp_path / "plain.jpg"
    Image.new("RGB", (10,10), "white").save(p)
    data = extract_exif(p)
    assert isinstance(data, ExifData)
    assert data.taken_at is None
    assert data.camera is None

def test_exif_parses_common_fields(tmp_path: Path):
    p = tmp_path / "with_exif.jpg"
    import piexif
    exif = {
        "0th": {piexif.ImageIFD.Make: b"Canon", piexif.ImageIFD.Model: b"EOS R6"},
        "Exif": {piexif.ExifIFD.DateTimeOriginal: b"2024:10:30 14:22:01"},
    }
    Image.new("RGB", (10,10), "white").save(p, exif=piexif.dump(exif))
    data = extract_exif(p)
    assert data.taken_at == "2024-10-30T14:22:01"
    assert data.camera == "Canon EOS R6"


def test_camera_join_dedupes_make_prefix():
    assert _join_camera("Canon", "Canon EOS RP") == "Canon EOS RP"
    assert _join_camera("Canon", "EOS RP") == "Canon EOS RP"
    assert _join_camera("", "iPhone 15") == "iPhone 15"
    assert _join_camera("Apple", "") == "Apple"
    assert _join_camera("", "") is None

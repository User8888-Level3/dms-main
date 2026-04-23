import subprocess
from pathlib import Path
import pytest
import piexif
from PIL import Image
from photo_index.thumbs import (
    make_thumbnail,
    make_thumbnail_raw,
    make_thumbnail_video,
    ThumbResult,
)

CR3_FIXTURE = Path("/Volumes/Pictures-Vol3/2025/061225/IMG_4709.CR3")


def _make_test_mp4(path: Path, seconds: int = 2, size: str = "800x600") -> None:
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", f"color=c=green:s={size}:d={seconds}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(seconds),
         str(path)],
        check=True, capture_output=True, timeout=30,
    )

def test_thumbnail_jpg_roundtrip(tmp_path: Path):
    src = tmp_path / "big.jpg"
    Image.new("RGB", (1600, 900), "blue").save(src, "JPEG", quality=90)
    out = tmp_path / "thumb.jpg"
    res = make_thumbnail(src, out, max_edge=400)
    assert isinstance(res, ThumbResult)
    assert out.exists()
    assert res.width == 1600 and res.height == 900
    with Image.open(out) as im:
        assert max(im.size) == 400
    # phash is 16 hex chars (64-bit)
    assert len(res.phash) == 16
    assert all(c in "0123456789abcdef" for c in res.phash)

def test_thumbnail_respects_orientation(tmp_path: Path):
    # Build an image with EXIF orientation=6 (rotated 90° CW by camera, meaning
    # the pixel data is 200 wide × 100 tall but camera says "render as portrait").
    # After exif_transpose, the portrait-orientation image should have h > w.
    src = tmp_path / "rot.jpg"
    im = Image.new("RGB", (200, 100), "red")
    # Pillow 12.x doesn't parse minimal hand-built TIFF EXIF reliably, so use
    # piexif.dump() per spec fallback — same outcome.
    exif_dict = {"0th": {piexif.ImageIFD.Orientation: 6}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    exif_bytes = piexif.dump(exif_dict)
    im.save(src, "JPEG", exif=exif_bytes)
    out = tmp_path / "rot_thumb.jpg"
    res = make_thumbnail(src, out, max_edge=400)
    # After orientation fix the ORIGINAL dims returned reflect the transposed dims
    # (exif_transpose runs before we measure — the result describes the upright image)
    assert res.width == 100 and res.height == 200
    with Image.open(out) as im2:
        w, h = im2.size
        assert h > w  # upright


@pytest.mark.skipif(not CR3_FIXTURE.exists(), reason="SMB CR3 fixture unavailable")
def test_thumbnail_raw_cr3(tmp_path: Path):
    out = tmp_path / "cr3_thumb.jpg"
    res = make_thumbnail_raw(CR3_FIXTURE, out, max_edge=400)
    assert isinstance(res, ThumbResult)
    assert out.exists()
    assert res.width > 0 and res.height > 0
    with Image.open(out) as im:
        assert max(im.size) == 400
    assert len(res.phash) == 16
    assert all(c in "0123456789abcdef" for c in res.phash)


def test_thumbnail_video_mp4(tmp_path: Path):
    src = tmp_path / "clip.mp4"
    _make_test_mp4(src, seconds=2, size="800x600")
    out = tmp_path / "vid_thumb.jpg"
    res = make_thumbnail_video(src, out, max_edge=400)
    assert isinstance(res, ThumbResult)
    assert out.exists()
    assert res.width == 800 and res.height == 600
    with Image.open(out) as im:
        assert max(im.size) == 400
    assert len(res.phash) == 16
    assert all(c in "0123456789abcdef" for c in res.phash)

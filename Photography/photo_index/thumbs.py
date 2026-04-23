import io
import subprocess
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageOps
import imagehash
import pillow_heif

from .retry import smb_retry

pillow_heif.register_heif_opener()


@dataclass(frozen=True)
class ThumbResult:
    width: int        # original dimensions (after orientation fix)
    height: int
    phash: str        # 16-char hex


def _encode_thumb(im: Image.Image, out: Path, max_edge: int, quality: int) -> ThumbResult:
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    orig_w, orig_h = im.size
    phash = str(imagehash.phash(im))
    im.thumbnail((max_edge, max_edge), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=quality, progressive=True, optimize=True)
    return ThumbResult(width=orig_w, height=orig_h, phash=phash)


@smb_retry()
def make_thumbnail(src: Path, out: Path, max_edge: int = 400, quality: int = 82) -> ThumbResult:
    with Image.open(src) as im:
        return _encode_thumb(im, out, max_edge, quality)


_RAW_PREVIEW_TAGS = ("-PreviewImage", "-JpgFromRaw", "-ThumbnailImage")


@smb_retry()
def make_thumbnail_video(src: Path, out: Path, max_edge: int = 400, quality: int = 82,
                         frame_at: str = "1") -> ThumbResult:
    """Extract a frame at `frame_at` seconds via ffmpeg, then encode a thumbnail."""
    r = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
         "-ss", frame_at, "-i", str(src),
         "-vframes", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
        capture_output=True, timeout=60,
    )
    if r.returncode != 0 or not r.stdout:
        # Retry at t=0 — short clips may be shorter than frame_at
        r = subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
             "-i", str(src),
             "-vframes", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
            capture_output=True, timeout=60,
        )
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError(f"ffmpeg could not extract frame from {src.name}: "
                           f"rc={r.returncode} stderr={r.stderr[:200]!r}")
    with Image.open(io.BytesIO(r.stdout)) as im:
        return _encode_thumb(im, out, max_edge, quality)


@smb_retry()
def make_thumbnail_raw(src: Path, out: Path, max_edge: int = 400, quality: int = 82) -> ThumbResult:
    """Extract embedded preview from a RAW file via exiftool, then encode a thumbnail.

    Tries PreviewImage, then JpgFromRaw, then ThumbnailImage. Raises if all empty.
    """
    preview: bytes = b""
    last_err: str | None = None
    for tag in _RAW_PREVIEW_TAGS:
        try:
            r = subprocess.run(
                ["exiftool", "-b", tag, str(src)],
                capture_output=True, timeout=30,
            )
        except subprocess.TimeoutExpired as e:
            last_err = f"timeout on {tag}: {e}"
            continue
        if r.returncode == 0 and r.stdout:
            preview = r.stdout
            break
        last_err = f"{tag}: rc={r.returncode} stderr={r.stderr[:200]!r}"
    if not preview:
        raise RuntimeError(f"no embedded preview in {src.name}: {last_err}")
    with Image.open(io.BytesIO(preview)) as im:
        return _encode_thumb(im, out, max_edge, quality)

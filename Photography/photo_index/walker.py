from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

IMAGE_EXTS = {"jpg", "jpeg", "png", "heic", "heif"}
RAW_EXTS   = {"cr3", "cr2", "arw", "nef", "dng", "orf", "rw2"}
VIDEO_EXTS = {"mp4", "mov", "m4v"}
ALL_EXTS   = IMAGE_EXTS | RAW_EXTS | VIDEO_EXTS
SKIP_DIRS  = {"#recycle", ".index", "@eaDir", ".Trashes", ".Spotlight-V100"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}


@dataclass(frozen=True)
class FileRecord:
    path: Path
    year: int
    event_folder: str
    filename: str
    ext: str
    kind: str  # image | raw | video
    size: int
    mtime: float


def _classify(ext: str) -> str | None:
    e = ext.lower()
    if e in IMAGE_EXTS: return "image"
    if e in RAW_EXTS:   return "raw"
    if e in VIDEO_EXTS: return "video"
    return None


def walk_year_folder(year_dir: Path) -> Iterator[FileRecord]:
    """Yield FileRecord for every indexable file under year_dir/<event>/...

    Assumes year_dir is named YYYY (e.g. /Volumes/Pictures-Vol3/2024)."""
    try:
        year = int(year_dir.name)
    except ValueError:
        raise ValueError(f"Expected year folder name YYYY, got {year_dir.name!r}")

    for event_dir in sorted(p for p in year_dir.iterdir() if p.is_dir()):
        if event_dir.name in SKIP_DIRS:
            continue
        for p in event_dir.rglob("*"):
            if not p.is_file():
                continue
            if p.name in SKIP_NAMES or p.name.startswith("._"):
                continue
            if any(part in SKIP_DIRS for part in p.relative_to(event_dir).parts):
                continue
            ext = p.suffix.lstrip(".").lower()
            kind = _classify(ext)
            if kind is None:
                continue
            st = p.stat()
            yield FileRecord(
                path=p,
                year=year,
                event_folder=event_dir.name,
                filename=p.name,
                ext=ext,
                kind=kind,
                size=st.st_size,
                mtime=st.st_mtime,
            )

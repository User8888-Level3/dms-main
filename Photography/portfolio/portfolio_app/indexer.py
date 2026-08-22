"""Portfolio indexer — walks /Volumes/photo, hashes, writes derivatives, seeds visibility.

CLI: python -m portfolio_app.indexer [--limit N] [--folder NAME] [--workers N] [--reseed]

Ground rules (SPEC.md § indexer.py):
- `folder` = NFC-normalized top-level dir name; every stored name/path is NFC
  (macOS SMB reports NFD — "Cancún" decomposed).
- Seed visibility/artwork ONLY on first insert. Re-index NEVER touches
  visibility/is_artwork — manual admin choices are sacred.
- Vanished files get `missing=1`; rows are never deleted (shares reference them).
- Incremental: skip when the DB row matches (mtime, bytes) and both derivative
  JPEGs exist. Workers do the NAS-heavy work; the main thread owns all DB writes
  and commits every `config.COMMIT_BATCH` results.
"""
import argparse
import hashlib
import io
import subprocess
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

from PIL import Image, ImageOps
import pillow_heif

from . import config, db
from .retry import smb_retry

pillow_heif.register_heif_opener()

_SKIP_NAMES = {"Thumbs.db", "desktop.ini"}
_EXIF_DATETIME_ORIGINAL = 36867  # DateTimeOriginal (lives in the Exif sub-IFD)
_EXIF_IFD = 0x8769


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


@dataclass(frozen=True)
class FileRecord:
    path: Path        # real on-disk path (as reported by the walk — used for I/O)
    folder: str       # NFC top-level collection name
    filename: str     # NFC
    ext: str          # lowercase, with dot
    kind: str         # 'image' | 'video'
    bytes: int
    mtime: float


@dataclass
class Result:
    rec: FileRecord
    skipped: bool = False
    sha1: str | None = None
    width: int | None = None
    height: int | None = None
    taken_at: str | None = None
    error: str | None = None


# ------------------------------------------------------------------ walk ----

@smb_retry()
def _list_dir(p: Path) -> list[Path]:
    return sorted(p.iterdir())


@smb_retry()
def _list_tree(p: Path) -> list[Path]:
    return sorted(p.rglob("*"))


@smb_retry()
def _stat(p: Path):
    return p.stat()


def walk(folder_filter: str | None = None) -> Iterator[FileRecord]:
    """Yield every indexable file under PHOTO_MOUNT/<top folder>/... .

    Skips EXCLUDE_DIRS + dot-named dirs at any depth; skips hidden files,
    Thumbs.db/desktop.ini, wrong extensions, and 0-byte files."""
    for top in _list_dir(config.PHOTO_MOUNT):
        if not top.is_dir():
            continue
        folder = _nfc(top.name)
        if folder.startswith(".") or folder in config.EXCLUDE_DIRS:
            continue
        if folder_filter is not None and folder != folder_filter:
            continue
        for p in _list_tree(top):
            if not p.is_file():
                continue
            if p.name.startswith(".") or p.name in _SKIP_NAMES:
                continue
            sub_parts = p.relative_to(top).parts[:-1]
            if any(part.startswith(".") or part in config.EXCLUDE_DIRS for part in sub_parts):
                continue
            ext = p.suffix.lower()
            if ext in config.IMAGE_EXTS:
                kind = "image"
            elif ext in config.VIDEO_EXTS:
                kind = "video"
            else:
                continue
            st = _stat(p)
            if st.st_size == 0:
                continue
            yield FileRecord(path=p, folder=folder, filename=_nfc(p.name), ext=ext,
                             kind=kind, bytes=st.st_size, mtime=st.st_mtime)


# --------------------------------------------------------------- process ----

@smb_retry()
def _read_bytes(p: Path) -> bytes:
    """One SMB read: bytes feed both the sha1 and the decoder."""
    return p.read_bytes()


@smb_retry()
def _sha1_file(p: Path, chunk: int = 1 << 20) -> str:
    """Streaming sha1 (videos — never load a full video into RAM)."""
    h = hashlib.sha1()
    with p.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


@smb_retry()
def _video_frame_bytes(src: Path) -> bytes:
    """Extract a poster frame via ffmpeg at t=1s; retry t=0 for very short clips."""
    r = None
    for pre in (["-ss", "1"], []):
        r = subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
             *pre, "-i", str(src),
             "-vframes", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
            capture_output=True, timeout=60,
        )
        if r.returncode == 0 and r.stdout:
            return r.stdout
    raise RuntimeError(f"ffmpeg could not extract frame from {src.name}: "
                       f"rc={r.returncode} stderr={r.stderr[:200]!r}")


@smb_retry()
def _save_jpeg(im: Image.Image, out: Path, quality: int) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=quality, progressive=True, optimize=True)


def _encode_derivatives(im: Image.Image, sha1: str) -> tuple[int, int]:
    """Write display (1600/q85) then thumb (400/q82, from the display for speed).

    Returns original (width, height) after orientation fix."""
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    orig_w, orig_h = im.size
    display = im.copy()
    display.thumbnail((config.DISPLAY_EDGE, config.DISPLAY_EDGE), Image.LANCZOS)
    _save_jpeg(display, config.display_path(sha1), config.DISPLAY_Q)
    thumb = display.copy()
    thumb.thumbnail((config.THUMB_EDGE, config.THUMB_EDGE), Image.LANCZOS)
    _save_jpeg(thumb, config.thumb_path(sha1), config.THUMB_Q)
    return orig_w, orig_h


def _mtime_iso(mtime: float) -> str:
    return datetime.fromtimestamp(mtime).isoformat(timespec="seconds")


def _taken_at_from_exif(im: Image.Image) -> str | None:
    """EXIF DateTimeOriginal (tag 36867) → ISO8601, else None."""
    try:
        exif = im.getexif()
    except Exception:
        return None
    dto = exif.get(_EXIF_DATETIME_ORIGINAL)
    if not dto:
        try:
            dto = exif.get_ifd(_EXIF_IFD).get(_EXIF_DATETIME_ORIGINAL)
        except Exception:
            dto = None
    if isinstance(dto, bytes):
        dto = dto.decode("ascii", "ignore")
    if not isinstance(dto, str):
        return None
    s = dto.strip("\x00 ")
    # "YYYY:MM:DD HH:MM:SS" → "YYYY-MM-DDTHH:MM:SS"
    if len(s) >= 19 and s[4] == ":" and s[7] == ":":
        return s[:4] + "-" + s[5:7] + "-" + s[8:10] + "T" + s[11:19]
    return None


def _process(rec: FileRecord) -> Result:
    """Pure NAS/CPU work — safe in a worker thread. No DB access."""
    res = Result(rec=rec)
    try:
        if rec.kind == "video":
            res.sha1 = _sha1_file(rec.path)
            frame = _video_frame_bytes(rec.path)
            with Image.open(io.BytesIO(frame)) as im:
                res.width, res.height = _encode_derivatives(im, res.sha1)
            res.taken_at = _mtime_iso(rec.mtime)
        else:
            data = _read_bytes(rec.path)
            res.sha1 = hashlib.sha1(data).hexdigest()
            with Image.open(io.BytesIO(data)) as im:
                res.taken_at = _taken_at_from_exif(im) or _mtime_iso(rec.mtime)
                res.width, res.height = _encode_derivatives(im, res.sha1)
    except Exception as e:
        res.error = f"{type(e).__name__}: {e}"
    return res


def _worker(rec: FileRecord, known: tuple[float, int, str, int] | None) -> Result:
    """Skip-check (incl. derivative existence — SMB stats stay parallel) then process."""
    if known is not None:
        mtime, nbytes, sha1, missing = known
        if (not missing and sha1
                and abs(mtime - rec.mtime) < 1e-6 and nbytes == rec.bytes
                and config.thumb_path(sha1).exists()
                and config.display_path(sha1).exists()):
            return Result(rec=rec, skipped=True, sha1=sha1)
    return _process(rec)


# -------------------------------------------------------------- DB writes ---

def _upsert(conn, res: Result, inserted_ids: list[int]) -> str:
    """Insert or update one processed row. Main thread only. Returns 'ok'.

    - Every path is its own row — the same content in several folders means
      several rows (one visibility per folder membership); derivatives are
      shared on disk because they are keyed by sha1.
    - Existing path: update metadata; NEVER touch visibility/is_artwork.
    - Seed rule applies ONLY on first insert; newly inserted row ids are
      collected so the sensitivity pass can demote them afterwards."""
    rec = res.rec
    path_nfc = _nfc(config.canon_path(rec.path))  # DB always stores /Volumes/photo/…
    row = conn.execute("SELECT id FROM photos WHERE path=?", (path_nfc,)).fetchone()
    if row is not None:
        conn.execute("""
            UPDATE photos SET folder=?, filename=?, sha1=?, ext=?, kind=?,
                              width=?, height=?, bytes=?, mtime=?, taken_at=?,
                              indexed_at=?, missing=0
            WHERE id=?
        """, (rec.folder, rec.filename, res.sha1, rec.ext, rec.kind,
              res.width, res.height, rec.bytes, rec.mtime, res.taken_at,
              db.now_iso(), row["id"]))
    else:
        visibility = "public" if rec.folder in config.PUBLIC_SEED_FOLDERS else "private"
        is_artwork = 1 if rec.folder in config.ARTWORK_SEED_FOLDERS else 0
        cur = conn.execute("""
            INSERT INTO photos(path, folder, filename, sha1, ext, kind, width, height,
                               bytes, mtime, taken_at, visibility, is_artwork,
                               indexed_at, missing)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
        """, (path_nfc, rec.folder, rec.filename, res.sha1, rec.ext, rec.kind,
              res.width, res.height, rec.bytes, rec.mtime, res.taken_at,
              visibility, is_artwork, db.now_iso()))
        inserted_ids.append(cur.lastrowid)
    return "ok"


def _demote_sensitive(conn, inserted_ids: list[int]) -> int:
    """Privacy-first pass over rows INSERTED this run (auto-seeded only —
    manual admin choices are on older rows and are never touched here):
    demote public → private when the same content also lives in a sensitive
    folder (Family, Customers, …). Harv can still publish by hand."""
    if not inserted_ids:
        return 0
    sens = sorted(config.SENSITIVE_FOLDERS)
    if not sens:
        return 0
    sp = ",".join("?" * len(sens))
    demoted = 0
    for i in range(0, len(inserted_ids), 500):     # SQLite var limit safety
        chunk = inserted_ids[i:i + 500]
        ip = ",".join("?" * len(chunk))
        cur = conn.execute(f"""
            UPDATE photos SET visibility='private'
            WHERE id IN ({ip}) AND visibility='public'
              AND sha1 IN (SELECT sha1 FROM photos WHERE folder IN ({sp}))
        """, (*chunk, *sens))
        demoted += cur.rowcount
    conn.commit()
    return demoted


def _mark_missing(conn, seen_paths: set[str], folder: str | None) -> int:
    """Flag rows whose file vanished from the walked scope. Never deletes."""
    if folder is not None:
        rows = conn.execute("SELECT id, path FROM photos WHERE missing=0 AND folder=?",
                            (folder,)).fetchall()
    else:
        rows = conn.execute("SELECT id, path FROM photos WHERE missing=0").fetchall()
    gone = [(r["id"],) for r in rows if r["path"] not in seen_paths]
    if gone:
        conn.executemany("UPDATE photos SET missing=1 WHERE id=?", gone)
        conn.commit()
    return len(gone)


def reseed(conn) -> None:
    """--reseed: re-apply the seed rule to seed-folder rows still private/non-artwork.

    Rows an admin already made public / marked artwork are untouched; rows made
    private by hand in NON-seed folders are untouched (the rule only ever adds)."""
    changed = 0
    pub = sorted(config.PUBLIC_SEED_FOLDERS)
    ph = ",".join("?" * len(pub))
    sens = sorted(config.SENSITIVE_FOLDERS)
    sp = ",".join("?" * len(sens))
    # Same privacy-first rule as indexing: content that also lives in a
    # sensitive folder is never promoted automatically.
    not_sensitive = f"AND sha1 NOT IN (SELECT sha1 FROM photos WHERE folder IN ({sp}))"
    for r in conn.execute(
            f"SELECT folder, COUNT(*) AS c FROM photos "
            f"WHERE visibility='private' AND folder IN ({ph}) {not_sensitive} "
            f"GROUP BY folder", (*pub, *sens)):
        print(f"reseed: {r['folder']} → {r['c']} photo(s) private → public")
        changed += r["c"]
    conn.execute(f"UPDATE photos SET visibility='public' "
                 f"WHERE visibility='private' AND folder IN ({ph}) {not_sensitive}",
                 (*pub, *sens))
    art = sorted(config.ARTWORK_SEED_FOLDERS)
    pa = ",".join("?" * len(art))
    for r in conn.execute(
            f"SELECT folder, COUNT(*) AS c FROM photos "
            f"WHERE is_artwork=0 AND folder IN ({pa}) GROUP BY folder", art):
        print(f"reseed: {r['folder']} → {r['c']} photo(s) marked artwork")
        changed += r["c"]
    conn.execute(f"UPDATE photos SET is_artwork=1 "
                 f"WHERE is_artwork=0 AND folder IN ({pa})", art)
    conn.commit()
    print(f"reseed: {changed} row(s) changed" if changed else "reseed: nothing to change")


# ------------------------------------------------------------------- CLI ----

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="portfolio_app.indexer",
        description="Index /Volumes/photo into the portfolio DB (incremental).")
    ap.add_argument("--limit", type=int, default=None,
                    help="process at most N files (skips the missing-file pass)")
    ap.add_argument("--folder", default=None,
                    help="only this top-level collection")
    ap.add_argument("--workers", type=int, default=config.WORKERS,
                    help=f"thread pool size (default {config.WORKERS})")
    ap.add_argument("--reseed", action="store_true",
                    help="re-apply the seed visibility/artwork rule to seed-folder "
                         "rows still private/non-artwork, then exit (no walk)")
    args = ap.parse_args(argv)

    config.ensure_dirs()
    conn = db.connect()

    if args.reseed:
        reseed(conn)
        return 0

    if not config.PHOTO_MOUNT.exists():
        print(f"error: {config.PHOTO_MOUNT} is not mounted", file=sys.stderr)
        return 2

    folder_arg = _nfc(args.folder) if args.folder else None
    t0 = time.time()
    print(f"walking {config.PHOTO_MOUNT} ...", flush=True)
    records = list(walk(folder_arg))
    if args.limit is not None:
        records = records[:args.limit]
    total = len(records)
    print(f"{total} file(s) to consider", flush=True)

    known = {r["path"]: (r["mtime"], r["bytes"], r["sha1"], r["missing"])
             for r in conn.execute("SELECT path, mtime, bytes, sha1, missing FROM photos")}

    ok = skipped = errors = 0
    pending = 0
    inserted_ids: list[int] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = [ex.submit(_worker, rec, known.get(_nfc(config.canon_path(rec.path))))
                for rec in records]
        done = 0
        for fut in as_completed(futs):
            res = fut.result()
            done += 1
            if res.skipped:
                status = "skip"
                skipped += 1
            elif res.error:
                status = "ERR"
                errors += 1
                print(f"[{done}/{total}] {res.rec.folder}/{res.rec.filename} "
                      f"ERROR {res.error}", flush=True)
            else:
                status = _upsert(conn, res, inserted_ids)
                ok += 1
                pending += 1
                if pending % config.COMMIT_BATCH == 0:
                    conn.commit()
            if done % 25 == 0 or done == total:
                print(f"[{done}/{total}] {res.rec.folder}/{res.rec.filename} {status}",
                      flush=True)
    conn.commit()

    demoted = _demote_sensitive(conn, inserted_ids)
    if demoted:
        print(f"privacy: {demoted} auto-seeded photo(s) demoted to private "
              f"(same content also lives in a sensitive folder)")

    missing = 0
    if args.limit is None:
        seen = {_nfc(config.canon_path(rec.path)) for rec in records}
        missing = _mark_missing(conn, seen, folder_arg)

    db.meta_set(conn, "last_index_at", db.now_iso())
    dt = time.time() - t0
    print(f"done: {total} walked · {ok} indexed · {skipped} skipped · "
          f"{errors} errors · {missing} marked missing · {dt:.1f}s")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

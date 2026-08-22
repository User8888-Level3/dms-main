"""Central configuration for the portfolio app (see SPEC.md § config.py).

All paths are absolute. Photos live on the Synology share at PHOTO_MOUNT and
are never copied off it — derivatives (thumb/display JPEGs) live in a hidden
`.portfolio` folder on the same share, addressed by sha1.
"""
import os
import unicodedata
from pathlib import Path

ROOT          = Path("/Users/harvinderbalu1/Library/CloudStorage/GoogleDrive-harvinder.balu@gmail.com/My Drive/ClaudeCode/Photography/portfolio")

# Canonical mount prefix — DB paths ALWAYS use this, whatever macOS mounted.
CANON_MOUNT   = Path("/Volumes/photo")


def _resolve_mount() -> Path:
    """Actual mountpoint of the SMB 'photo' share.

    macOS sometimes strands a dead, unreadable stub at /Volumes/photo and
    remounts the share at /Volumes/photo-1 (-2, …). Pick the first candidate
    that is really readable; fall back to the canonical path."""
    candidates = [CANON_MOUNT] + [Path(f"/Volumes/photo-{i}") for i in (1, 2, 3)]
    for p in candidates:
        try:
            if p.is_dir() and os.access(p, os.R_OK | os.X_OK) and any(p.iterdir()):
                return p
        except OSError:
            continue
    return CANON_MOUNT


PHOTO_MOUNT   = _resolve_mount()                    # actual (resolved at import)
DERIV_ROOT    = PHOTO_MOUNT / ".portfolio"          # thumbs+display live ON the NAS share


def canon_path(real: "Path | str") -> str:
    """Translate an actual on-disk path to the canonical /Volumes/photo form (for the DB)."""
    s = str(real)
    root = str(PHOTO_MOUNT)
    return str(CANON_MOUNT) + s[len(root):] if s.startswith(root) else s


def real_path(canon: "Path | str") -> Path:
    """Translate a canonical DB path to wherever the share is mounted right now."""
    s = str(canon)
    root = str(CANON_MOUNT)
    return Path(str(PHOTO_MOUNT) + s[len(root):]) if s.startswith(root) else Path(s)
THUMB_DIR     = DERIV_ROOT / "thumb"                # <sha1[:2]>/<sha1>.jpg  (400px, q82)
DISPLAY_DIR   = DERIV_ROOT / "display"              # <sha1[:2]>/<sha1>.jpg  (1600px, q85)
DB_PATH       = ROOT / "data" / "portfolio.db"
HOST = os.environ.get("PORTFOLIO_HOST", "127.0.0.1")
PORT = int(os.environ.get("PORTFOLIO_PORT", "8770"))
BASE_URL = os.environ.get("PORTFOLIO_BASE_URL", "http://127.0.0.1:8770")  # share links

# ── deployment switches (all env-driven; local run needs none of them) ──────
# Public hosting:  PORTFOLIO_PUBLIC=1 PORTFOLIO_ADMIN_TOKEN=<long random secret>
#   PORTFOLIO_PUBLIC=1  → localhost is NOT trusted as admin (reverse proxies
#                         connect from localhost — trusting it would hand
#                         every visitor the admin panel).
#   ADMIN_TOKEN         → enables /admin/login; the login sets an HttpOnly
#                         cookie holding this token.
ADMIN_TOKEN = os.environ.get("PORTFOLIO_ADMIN_TOKEN") or None
ALLOW_LOCALHOST_ADMIN = os.environ.get("PORTFOLIO_PUBLIC", "") != "1"
SITE_NAME     = "HARV BALU"

# THE INSTRUMENT (the overture of /work): the photograph the sensor records
# at the end of the sequence. Any public photo's sha1; the static exporter
# bundles its display derivative into the deploy so the overture never waits
# on the home server. Epoch is the only caption the world allows.
INSTRUMENT_PHOTO_SHA1  = "d7bc3b686e0a425cf9c68f99875b6b2e2502a268"   # Cosmology, a gold moon
INSTRUMENT_PHOTO_EPOCH = "2016 · Oct 17"
CONTACT_EMAIL = "homes@HarvRealtor.com"
INSTAGRAM_URL = "https://www.instagram.com/harvrealtor/"
EXCLUDE_DIRS  = {"#recycle", "@eaDir", ".portfolio"}   # plus any name starting with "."
IMAGE_EXTS    = {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff"}
VIDEO_EXTS    = {".mp4", ".mov", ".avi"}

# macOS SMB reports names in NFD ("Cancún" decomposed) — every comparison against
# these sets happens on NFC-normalized names, and the sets themselves are
# normalized here so the source-file encoding can never break matching.
PUBLIC_SEED_FOLDERS = {unicodedata.normalize("NFC", n) for n in {
    "AI Generated", "Cosmology", "Half Moon Bay", "Cancún", "Niagara Falls",
    "Monterey Bay Aquarium", "Alviso Marina County Park", "Ed R. Levin County Park",
    "New York City"}}
ARTWORK_SEED_FOLDERS = {unicodedata.normalize("NFC", n) for n in {
    "AI Generated", "Cosmology"}}
# Content that ALSO lives in any of these folders is NEVER auto-seeded public,
# even when a copy sits in a public-seed folder (privacy-first — Harv's rule).
# Harv can still publish such a photo by hand in the admin panel.
SENSITIVE_FOLDERS = {unicodedata.normalize("NFC", n) for n in {
    "Family", "Customers", "PhotoLibrary"}}

THUMB_EDGE, THUMB_Q     = 400, 82
DISPLAY_EDGE, DISPLAY_Q = 1600, 85
WORKERS = 8

COMMIT_BATCH    = 50    # indexer: DB commit cadence (results per commit)
SMB_RETRY       = 3     # attempts for flaky NAS reads (see retry.py)
SMB_RETRY_DELAY = 2.0   # seconds, exponential backoff multiplier


def thumb_path(sha1: str) -> Path:
    """.portfolio/thumb/<sha1[:2]>/<sha1>.jpg"""
    return THUMB_DIR / sha1[:2] / f"{sha1}.jpg"


def display_path(sha1: str) -> Path:
    """.portfolio/display/<sha1[:2]>/<sha1>.jpg"""
    return DISPLAY_DIR / sha1[:2] / f"{sha1}.jpg"


def ensure_dirs() -> None:
    """Create runtime dirs that live in the repo (the NAS dirs are made lazily)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

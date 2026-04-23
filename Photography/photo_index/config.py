from pathlib import Path

ROOT       = Path("/Users/harvinderbalu1/Library/CloudStorage/OneDrive-Personal/ClaudeCode/Photography")
MOUNT      = Path("/Volumes/Pictures-Vol3")
DB_PATH    = ROOT / "index.db"
THUMB_ROOT = MOUNT / ".index" / "thumbs"
SITE_DIR   = ROOT / "site"
LOG_DIR    = ROOT / "logs"
STATE_PATH = ROOT / "SESSION-STATE.md"

THUMB_MAX_EDGE = 400
THUMB_QUALITY  = 82
WORKERS        = 12
COMMIT_BATCH   = 100
SMB_RETRY      = 3
SMB_RETRY_DELAY = 2.0  # seconds, exponential backoff multiplier


def thumb_path(sha1: str, year: int, event: str) -> Path:
    """.index/thumbs/<year>/<event>/<sha1[:2]>/<sha1>.jpg"""
    return THUMB_ROOT / str(year) / event / sha1[:2] / f"{sha1}.jpg"


def thumb_rel(sha1: str, year: int, event: str) -> str:
    return f"{year}/{event}/{sha1[:2]}/{sha1}.jpg"


def ensure_dirs() -> None:
    for d in [LOG_DIR, SITE_DIR, SITE_DIR/"years", SITE_DIR/"photo", SITE_DIR/"assets", THUMB_ROOT]:
        d.mkdir(parents=True, exist_ok=True)

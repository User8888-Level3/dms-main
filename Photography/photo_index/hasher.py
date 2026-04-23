import hashlib
from pathlib import Path

from .retry import smb_retry


@smb_retry()
def sha1_of_file(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with p.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


@smb_retry()
def sha1_and_bytes(p: Path) -> tuple[str, bytes]:
    """Return (sha1, raw_bytes). Use when we'll also decode the file.

    Avoids a second SMB read."""
    data = p.read_bytes()
    return hashlib.sha1(data).hexdigest(), data

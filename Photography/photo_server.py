#!/usr/bin/env python
"""Local dashboard server for the photography archive.

Serves everything under site/ as static files (identical to `python -m http.server`)
AND adds two POST endpoints that let the dashboard's Lightbox open the real photo
or reveal it in Finder:

    POST /api/open    {"path": "/Volumes/Pictures-Vol3/…"}   → `open <path>`
    POST /api/reveal  {"path": "/Volumes/Pictures-Vol3/…"}   → `open -R <path>`

Only paths under the configured MOUNT (default /Volumes/Pictures-Vol3/) are allowed.
Binds to 127.0.0.1 only.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlparse

from photo_index import config

HOST = "127.0.0.1"
PORT = 8765
SITE_DIR = str(config.SITE_DIR)
ALLOWED_PREFIX = str(config.MOUNT) + os.sep  # "/Volumes/Pictures-Vol3/"


class Handler(SimpleHTTPRequestHandler):
    """Static files + two JSON POST endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SITE_DIR, **kwargs)

    def end_headers(self):
        # Without Cache-Control, browsers heuristically cache old pages for
        # days (site regenerates but the browser keeps showing stale HTML/CSS).
        # Thumbs are content-addressed by SHA-1, so those may cache forever.
        if self.path.startswith("/thumbs/"):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def translate_path(self, path: str) -> str:
        # Serve /thumbs/ straight from the NAS thumb root. Google Drive keeps
        # destroying the site/thumbs symlink (it syncs symlinks with empty
        # targets), so we must not depend on it.
        parsed = urlparse(path)
        if parsed.path.startswith("/thumbs/"):
            rel = os.path.normpath(unquote(parsed.path[len("/thumbs/"):])).lstrip("/")
            candidate = (config.THUMB_ROOT / rel).resolve()
            if str(candidate).startswith(str(config.THUMB_ROOT)):
                return str(candidate)
        return super().translate_path(path)

    # ─── POST /api/{open,reveal} ───────────────────────────────────────────

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path not in ("/api/open", "/api/reveal"):
            self._respond(404, {"error": "unknown endpoint"})
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > 8192:
            self._respond(400, {"error": "missing or oversized body"})
            return
        try:
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            body = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._respond(400, {"error": "invalid json"})
            return

        path = body.get("path") or ""
        if not isinstance(path, str) or not path:
            self._respond(400, {"error": "missing path"})
            return
        if not path.startswith(ALLOWED_PREFIX):
            self._respond(403, {"error": "path outside allowed volume"})
            return
        if not Path(path).exists():
            self._respond(404, {"error": "file not found on disk"})
            return

        argv = ["open", "-R", path] if parsed.path == "/api/reveal" else ["open", path]
        try:
            subprocess.run(argv, check=True, timeout=8)
        except FileNotFoundError:
            self._respond(500, {"error": "macOS `open` command unavailable"})
            return
        except subprocess.CalledProcessError as e:
            self._respond(500, {"error": f"open failed (exit {e.returncode})"})
            return
        except subprocess.TimeoutExpired:
            self._respond(504, {"error": "open timed out"})
            return
        self._respond(200, {"ok": True})

    # ─── helpers ───────────────────────────────────────────────────────────

    def _respond(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except BrokenPipeError:
            pass

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


class _ReusableServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    print("================================================", file=sys.stderr, flush=True)
    print(" Photo Archive Dashboard", file=sys.stderr, flush=True)
    print(f" URL:  http://{HOST}:{PORT}/", file=sys.stderr, flush=True)
    print(f" Root: {SITE_DIR}", file=sys.stderr, flush=True)
    print(f" Open API restricted to: {ALLOWED_PREFIX}", file=sys.stderr, flush=True)
    print("================================================", file=sys.stderr, flush=True)
    server = _ReusableServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[photo-archive] stopped", file=sys.stderr, flush=True)
        server.server_close()


if __name__ == "__main__":
    main()

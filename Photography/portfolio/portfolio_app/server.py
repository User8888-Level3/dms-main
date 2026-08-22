#!/usr/bin/env python
"""HTTP server for the HARV BALU photo portfolio.

Stdlib-only ThreadingHTTPServer bound to 127.0.0.1:8770. Routes:

    GET  /                       landing page (scattered collage, giant type)
    GET  /work                   public collections grid
    GET  /c/<folder>             one collection (public photos only)
    GET  /s/<token>              share-link page (404 unknown / 410 dead)
    GET  /media/<kind>/<sha1>    thumb | display | orig — THE security chokepoint
    GET  /admin                  admin panel (localhost-gated)
    GET  /healthz                {"ok": true, "photos": N}
    GET  /static/*               static assets (traversal-safe)

    GET  /api/admin/state        folders + share count          (admin)
    GET  /api/admin/photos       photos of one folder           (admin)
    GET  /api/admin/shares       all share links                (admin)
    POST /api/admin/visibility   bulk public/private            (admin)
    POST /api/admin/artwork      bulk artwork flag              (admin)
    POST /api/admin/share        mint a share link              (admin)
    POST /api/admin/revoke       revoke a share link            (admin)

Every filesystem access driven by client input goes through the sha1 regex
``^[0-9a-f]{40}$`` + a DB lookup — no client-supplied path ever touches disk.
Private photos are served only to admin or via a valid share token (``?t=``).
"""
from __future__ import annotations

import hmac
import json
import mimetypes
import os
import re
import sqlite3
import sys
import unicodedata
from contextlib import closing
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from . import config, db
from .render import html_escape, render

# ─── constants ─────────────────────────────────────────────────────────────

CHUNK = 64 * 1024          # streaming chunk size
MAX_BODY = 64 * 1024       # JSON body limit

SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
MEDIA_RE = re.compile(r"^/media/(thumb|display|orig)/([0-9a-f]{40})(?:\.jpg)?$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

STATIC_DIR = config.ROOT / "static"

EXPIRES_HOURS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}

CACHE_IMMUTABLE = "public, max-age=31536000, immutable"  # sha1-addressed derivatives
CACHE_PRIVATE = "private, no-store"

# data-speed values for collage tiles, varied across the 0.05–0.35 band so
# neighbouring tiles never share a parallax rate.
TILE_SPEEDS = ("0.12", "0.28", "0.07", "0.22", "0.31", "0.09", "0.18",
               "0.26", "0.05", "0.33", "0.15", "0.24", "0.10", "0.35")
COLLAGE_CAP = 14

# ── Meridian survey helpers (work.html / collection.html, 2026-08 redesign) ──
# The static exporter (export_static.py) mirrors these; keep the markup in
# lockstep so the live preview matches the deployed site.

ROMAN_NUMERALS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
                  "XI", "XII", "XIII", "XIV", "XV")
MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _roman(n: int) -> str:
    return ROMAN_NUMERALS[n - 1] if 1 <= n <= len(ROMAN_NUMERALS) else str(n)


def _epoch_label(first_iso: str, last_iso: str) -> str:
    """'2003 — 2022' for a span, 'Feb 2023' for one month, '2022' for one year."""
    fy, fm = first_iso[:4], first_iso[5:7]
    ly, lm = last_iso[:4], last_iso[5:7]
    if fy != ly:
        return f"{fy} — {ly}"
    if fm != lm:
        return fy
    try:
        return f"{MONTH_ABBR[int(fm) - 1]} {fy}"
    except (ValueError, IndexError):
        return fy

ABOUT_HTML = (
    "<p>BAY AREA PHOTOGRAPHER CHASING LIGHT ACROSS LANDSCAPES, WILDLIFE, "
    "COSMOLOGY, TRAVEL, AND AI-GENERATED ART. FROM THE PACIFIC COAST TO THE "
    "NIGHT SKY — SHOT SLOWLY, EDITED QUIETLY, SHARED RARELY.</p>"
)

_404_HTML = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    "<title>404 — HARV BALU</title><style>"
    "body{margin:0;min-height:100vh;display:grid;place-items:center;"
    "background:#F2EFE9;color:#0B0B0A;font-family:system-ui,sans-serif}"
    "h1{font-size:4rem;margin:0 0 .5rem;letter-spacing:-.02em}"
    "a{color:inherit}</style></head><body><div>"
    "<h1>404</h1><p>Nothing here.</p><p><a href=\"/\">HARV BALU</a></p>"
    "</div></body></html>"
)

# ─── small helpers ─────────────────────────────────────────────────────────


def _nfc(name: str) -> str:
    """NFC-normalize a folder/file name (macOS SMB reports NFD)."""
    return unicodedata.normalize("NFC", name)


def _rget(row, key: str, default=None):
    """Tolerant column access for sqlite3.Row *or* plain dict rows."""
    if row is None:
        return default
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value) -> datetime | None:
    """ISO8601 string → aware datetime (naive treated as UTC); None on junk."""
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _fmt_date(iso) -> str:
    """ISO timestamp → 'June 12, 2024' (empty string when unparseable)."""
    dt = _parse_iso(iso)
    if dt is None:
        return ""
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


def _fmt_local_date(iso) -> str:
    """ISO UTC timestamp → local-timezone 'June 12, 2024'."""
    dt = _parse_iso(iso)
    if dt is None:
        return ""
    loc = dt.astimezone()
    return f"{loc.strftime('%B')} {loc.day}, {loc.year}"


def _conn() -> sqlite3.Connection:
    """Fresh per-request connection with dict-style row access."""
    conn = db.connect()
    conn.row_factory = sqlite3.Row
    return conn


def is_admin(handler: BaseHTTPRequestHandler) -> bool:
    """Admin gate: localhost (when allowed) or the ``adm`` cookie token."""
    ip = handler.client_address[0]
    if config.ALLOW_LOCALHOST_ADMIN and ip == "127.0.0.1":
        return True
    token = config.ADMIN_TOKEN
    if not token:
        return False
    cookie = SimpleCookie()
    try:
        cookie.load(handler.headers.get("Cookie", "") or "")
    except Exception:
        return False
    morsel = cookie.get("adm")
    return bool(morsel and hmac.compare_digest(morsel.value, token))


# ── login throttle (public hosting) ────────────────────────────────────────
# Tiny in-memory limiter: per-IP failed attempts; locked out after LOGIN_MAX
# failures within LOGIN_WINDOW seconds. Enough to blunt online guessing of a
# long random token; not a substitute for HTTPS + a strong ADMIN_TOKEN.
LOGIN_MAX = 10
LOGIN_WINDOW = 600.0
_login_fails: dict[str, list[float]] = {}
_login_lock = __import__("threading").Lock()


def _login_throttled(ip: str) -> bool:
    now = __import__("time").monotonic()
    with _login_lock:
        lst = [t for t in _login_fails.get(ip, ()) if now - t < LOGIN_WINDOW]
        _login_fails[ip] = lst
        return len(lst) >= LOGIN_MAX


def _login_record_failure(ip: str) -> None:
    now = __import__("time").monotonic()
    with _login_lock:
        _login_fails.setdefault(ip, []).append(now)


_LOGIN_HTML = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    '<meta name="robots" content="noindex, nofollow">'
    "<title>Sign in — HARV BALU</title><style>"
    "body{margin:0;min-height:100vh;display:grid;place-items:center;"
    "background:#0E0D0B;color:#F2EFE9;font-family:ui-monospace,monospace}"
    "form{display:grid;gap:12px;width:min(320px,86vw)}"
    "h1{font-size:1rem;letter-spacing:.2em;font-weight:500;margin:0 0 4px}"
    "input{background:#1a1917;color:#F2EFE9;border:1px solid #3a3833;"
    "padding:12px 14px;font:inherit;border-radius:0}"
    "input:focus-visible{outline:2px solid #D4AF37;outline-offset:1px}"
    "button{background:#D4AF37;color:#0E0D0B;border:0;padding:12px 14px;"
    "font:inherit;font-weight:700;letter-spacing:.12em;cursor:pointer}"
    "p.err{color:#e2574a;margin:0;font-size:.85rem;min-height:1em}"
    "</style></head><body><form method=\"post\" action=\"/admin/login\">"
    "<h1>HARV BALU — ADMIN</h1><p class=\"err\">{err}</p>"
    '<input type="password" name="token" placeholder="access token" '
    'autocomplete="current-password" autofocus>'
    "<button type=\"submit\">SIGN IN</button></form></body></html>"
)


# ─── request handler ───────────────────────────────────────────────────────


class Handler(BaseHTTPRequestHandler):
    """All routes for the portfolio: pages, media chokepoint, admin API."""

    server_version = "PortfolioHTTP/1.0"
    protocol_version = "HTTP/1.1"  # keep-alive; every response sets Content-Length

    def end_headers(self) -> None:
        # Share pages embed ?t=<token> URLs — never leak them via Referer
        # (fonts.googleapis.com requests, outbound clicks). Applied globally.
        self.send_header("Referrer-Policy", "same-origin")
        super().end_headers()

    # ── entry points ──────────────────────────────────────────────────────

    def do_GET(self) -> None:  # noqa: N802
        self._safe(self._route_get, head=False)

    def do_HEAD(self) -> None:  # noqa: N802
        self._safe(self._route_get, head=True)

    def do_POST(self) -> None:  # noqa: N802
        self._safe(self._route_post)

    def _safe(self, fn, **kwargs) -> None:
        """Run a router; a crash becomes a logged 500 instead of a dead socket.

        Also owns the per-request DB connection: opened lazily via ``_db()`` and
        always closed here — including between keep-alive requests on one socket.
        """
        self._req_conn = None
        try:
            fn(**kwargs)
        except (ConnectionError, BrokenPipeError):
            pass  # client went away mid-response
        except Exception as e:  # pragma: no cover — last-resort guard
            sys.stderr.write(f"[portfolio] 500 {self.path}: {e!r}\n")
            try:
                self._respond_json(500, {"error": "internal error"})
            except Exception:
                pass
        finally:
            if getattr(self, "_req_conn", None) is not None:
                try:
                    self._req_conn.close()
                except Exception:
                    pass
                self._req_conn = None

    def _db(self) -> sqlite3.Connection:
        """Lazy per-request DB connection (closed in ``_safe``). db.py helpers
        all take the connection as their first argument."""
        if getattr(self, "_req_conn", None) is None:
            self._req_conn = _conn()
        return self._req_conn

    # ── GET routing ───────────────────────────────────────────────────────

    def _route_get(self, head: bool) -> None:
        parsed = urlparse(self.path)
        raw = parsed.path
        query = parse_qs(parsed.query)

        media = MEDIA_RE.match(raw)
        if media:
            self._serve_media(media.group(1), media.group(2), query, head)
        elif raw == "/":
            self._page_index(head)
        elif raw == "/work":
            self._page_work(head)
        elif raw.startswith("/c/"):
            self._page_collection(unquote(raw[len("/c/"):]), head)
        elif raw.startswith("/s/"):
            self._page_share(unquote(raw[len("/s/"):]), head)
        elif raw in ("/admin", "/admin/"):
            self._page_admin(head)
        elif raw == "/admin/login":
            self._page_login(head)
        elif raw == "/admin/logout":
            self._do_logout()
        elif raw == "/healthz":
            self._api_healthz()
        elif raw.startswith("/static/"):
            self._serve_static(raw, head)
        elif raw == "/api/admin/state":
            self._admin_gate_json() and self._api_state()
        elif raw == "/api/admin/photos":
            self._admin_gate_json() and self._api_photos(query)
        elif raw == "/api/admin/shares":
            self._admin_gate_json() and self._api_shares()
        else:
            self._respond_html(404, _404_HTML, head)

    # ── POST routing ──────────────────────────────────────────────────────

    def _route_post(self) -> None:
        raw = urlparse(self.path).path
        if raw == "/admin/login":       # form-encoded; exempt from the admin gate
            self._do_login()
            return
        handlers = {
            "/api/admin/visibility": self._api_visibility,
            "/api/admin/artwork": self._api_artwork,
            "/api/admin/share": self._api_share_create,
            "/api/admin/revoke": self._api_share_revoke,
        }
        handler = handlers.get(raw)
        if handler is None:
            self._respond_json(404, {"error": "unknown endpoint"})
            return
        if not self._admin_gate_json():
            return
        body = self._read_json_body()
        if body is None:
            return
        handler(body)

    # ── media chokepoint ──────────────────────────────────────────────────

    def _serve_media(self, kind: str, sha1: str, query: dict, head: bool) -> None:
        """Serve thumb/display/orig for one photo. ALL access control lives here."""
        if not SHA1_RE.match(sha1):  # belt-and-braces: MEDIA_RE already enforced
            self._respond_json(404, {"error": "not found"})
            return

        # One content hash may have several rows (same file in several folders,
        # each with its own visibility). Access rules over the whole set:
        #   public   — ANY live membership row is public
        #   token    — share row references ANY of the membership row ids
        rows = [r for r in db.photos_by_sha1(self._db(), sha1)
                if not _rget(r, "missing", 0)]
        if not rows:
            self._respond_json(404, {"error": "not found"})
            return
        photo = rows[0]

        visibility = "public" if any(
            _rget(r, "visibility") == "public" for r in rows) else "private"
        if visibility != "public" and not is_admin(self):
            token = (query.get("t") or [""])[0]
            share = db.get_share(self._db(), token) if token else None
            row_ids = {_rget(r, "id") for r in rows}
            allowed = (
                share is not None
                and _rget(share, "photo_id") in row_ids
                and db.share_valid(share)
            )
            if not allowed:
                self._respond_json(403, {"error": "forbidden"})
                return

        filename = str(_rget(photo, "filename", f"{sha1}{_rget(photo, 'ext', '')}"))
        if kind == "orig":
            # DB stores the canonical /Volumes/photo/… path; resolve to wherever
            # macOS actually mounted the share this boot (photo, photo-1, …).
            file_path = config.real_path(str(_rget(photo, "path", "")))
            ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        else:
            base = config.THUMB_DIR if kind == "thumb" else config.DISPLAY_DIR
            file_path = base / sha1[:2] / f"{sha1}.jpg"
            ctype = "image/jpeg"

        try:
            st = file_path.stat()
            fh = file_path.open("rb")
        except OSError:
            self._respond_json(404, {"error": "file unavailable"})
            return

        with fh:
            cache = CACHE_IMMUTABLE if (kind != "orig" and visibility == "public") \
                else CACHE_PRIVATE
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(st.st_size))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            if kind == "orig":
                self.send_header("Content-Disposition", _disposition(filename, sha1))
            self.end_headers()
            if head:
                return
            while True:
                chunk = fh.read(CHUNK)
                if not chunk:
                    break
                self.wfile.write(chunk)

    # ── static files ──────────────────────────────────────────────────────

    def _serve_static(self, raw: str, head: bool) -> None:
        rel = unquote(raw[len("/static/"):])
        if not rel or rel.startswith(("/", ".")) or "\\" in rel \
                or ".." in rel.split("/"):
            self._respond_html(404, _404_HTML, head)
            return
        root = STATIC_DIR.resolve()
        candidate = (STATIC_DIR / rel).resolve()
        if not str(candidate).startswith(str(root) + os.sep) or not candidate.is_file():
            self._respond_html(404, _404_HTML, head)
            return
        ctype = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        st = candidate.stat()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(st.st_size))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if head:
            return
        with candidate.open("rb") as fh:
            while True:
                chunk = fh.read(CHUNK)
                if not chunk:
                    break
                self.wfile.write(chunk)

    # ── HTML pages ────────────────────────────────────────────────────────

    def _base_ctx(self) -> dict:
        return {
            "site_name": html_escape(config.SITE_NAME),
            "hero_name": html_escape(config.SITE_NAME),
            "contact_email": html_escape(config.CONTACT_EMAIL),
            "instagram_url": html_escape(config.INSTAGRAM_URL),
            "year": datetime.now().year,
        }

    def _build_collection_cards(self) -> tuple[str, int, int]:
        """Public collection cards markup + (collection count, public photo total)."""
        cards: list[str] = []
        index = 0
        total_public = 0
        for f in db.all_folders(self._db()):
            public = int(_rget(f, "public", 0) or 0)
            if public <= 0:
                continue
            index += 1
            total_public += public
            name = str(_rget(f, "folder", ""))
            cover = str(_rget(f, "cover_sha1", "") or "")
            href = "/c/" + quote(name, safe="")
            img = (
                f'<img class="collection-cover" src="/media/display/{cover}.jpg" '
                f'alt="{html_escape(name)}" loading="lazy">'
            ) if SHA1_RE.match(cover) else ""
            cards.append(
                f'<a class="collection-card" href="{html_escape(href)}">{img}'
                f'<span class="collection-caption">{index:02d} — '
                f"{html_escape(name.upper())} · {public}</span></a>"
            )
        return "\n".join(cards), index, total_public

    def _page_index(self, head: bool) -> None:
        cards, n_collections, n_public = self._build_collection_cards()
        doc = render(
            "index.html",
            collage_tiles=_build_collage_tiles(),
            collection_cards=cards,
            collection_count=n_collections,
            photo_total=n_public,
            about_html=ABOUT_HTML,
            **self._base_ctx(),
        )
        self._respond_html(200, doc, head)

    def _survey_facts(self) -> tuple[list[dict], str, int, int]:
        """Meridian data: stations (newest last-observation first), span, totals."""
        conn = self._db()
        rows = conn.execute(
            "SELECT folder, COUNT(*) AS n, "
            "       MIN(substr(taken_at,1,10)) AS first_obs, "
            "       MAX(substr(taken_at,1,10)) AS last_obs "
            "FROM photos WHERE visibility='public' AND missing=0 "
            "GROUP BY folder ORDER BY last_obs DESC"
        ).fetchall()
        stations: list[dict] = []
        for r in rows:
            folder = str(r["folder"])
            cover = conn.execute(
                "SELECT sha1 FROM photos WHERE folder=? AND missing=0 "
                "AND visibility='public' ORDER BY taken_at DESC, id DESC LIMIT 1",
                (folder,),
            ).fetchone()
            first = str(r["first_obs"] or "")
            last = str(r["last_obs"] or "")
            stations.append({
                "folder": folder, "n": int(r["n"]),
                "cover": cover["sha1"] if cover else "",
                "label": _epoch_label(first, last) if first and last else "",
                "first": first, "last": last,
            })
        years = [s["first"][:4] for s in stations if s["first"]] + \
                [s["last"][:4] for s in stations if s["last"]]
        span = f"{min(years)} — {max(years)}" if years else ""
        total = sum(s["n"] for s in stations)
        return stations, span, len(stations), total

    def _page_work(self, head: bool) -> None:
        stations, span, n_coll, n_photos = self._survey_facts()
        parts: list[str] = []
        for i, s in enumerate(stations, start=1):
            href = "/c/" + quote(s["folder"], safe="")
            img = (
                f'<img class="station-plate" src="/media/display/{s["cover"]}.jpg" '
                f'alt="" loading="{"eager" if i == 1 else "lazy"}">'
            ) if SHA1_RE.match(s["cover"] or "") else ""
            parts.append(
                f'<li class="station">'
                f'<span class="station-tick" aria-hidden="true"></span>'
                f'<a class="station-link" href="{html_escape(href)}">'
                f'{img}'
                f'<span class="station-text">'
                f'<span class="station-name">{html_escape(s["folder"])}</span>'
                f'<span class="station-data">Chart {_roman(i)} · '
                f'{s["n"]} frames · {html_escape(s["label"])}</span>'
                f'</span>'
                f'</a></li>'
            )
        doc = render(
            "work.html",
            meridian_stations="\n".join(parts),
            survey_span=html_escape(span),
            collection_count=n_coll,
            photo_total=n_photos,
            instrument_photo=f"/media/display/{config.INSTRUMENT_PHOTO_SHA1}.jpg",
            instrument_epoch=html_escape(config.INSTRUMENT_PHOTO_EPOCH),
            **self._base_ctx(),
        )
        self._respond_html(200, doc, head)

    def _page_collection(self, folder_raw: str, head: bool) -> None:
        folder = _nfc(folder_raw)
        photos = db.public_photos(self._db(), folder=folder)
        if not photos:
            self._respond_html(404, _404_HTML, head)
            return
        stations, _, _, _ = self._survey_facts()
        chart_no = ""
        epoch_range = ""
        for i, s in enumerate(stations, start=1):
            if s["folder"] == folder:
                chart_no = _roman(i)
                epoch_range = s["label"]
                break
        tiles: list[str] = []
        seen: set[str] = set()  # same content twice in one folder → one tile
        for p in photos:
            sha1 = str(_rget(p, "sha1", ""))
            if not SHA1_RE.match(sha1) or sha1 in seen:
                continue
            seen.add(sha1)
            taken = html_escape(str(_rget(p, "taken_at", "") or ""))
            kind = html_escape(str(_rget(p, "kind", "image")))
            w, h = _rget(p, "width"), _rget(p, "height")
            dims = f' width="{int(w)}" height="{int(h)}"' if w and h else ""
            # No filename in the markup — alt is empty (decorative gallery img)
            # and there is no data-filename attribute to leak in the page source.
            loading = "eager" if len(seen) <= 4 else "lazy"
            tiles.append(
                f'<a class="ph" data-sha1="{sha1}" '
                f'data-taken="{taken}" data-kind="{kind}" '
                f'href="/media/display/{sha1}.jpg">'
                f'<img src="/media/thumb/{sha1}.jpg" alt=""{dims} '
                f'loading="{loading}"></a>'
            )
        doc = render(
            "collection.html",
            folder_name=html_escape(folder),
            collection_name=html_escape(folder),
            count=len(tiles),
            photo_count=len(tiles),
            chart_no=chart_no,
            epoch_range=html_escape(epoch_range),
            photo_tiles="\n".join(tiles),
            **self._base_ctx(),
        )
        self._respond_html(200, doc, head)

    def _page_share(self, token: str, head: bool) -> None:
        ctx = self._base_ctx()
        share = db.get_share(self._db(), token) if token else None
        if share is None:
            self._respond_html(404, render("expired.html", **ctx), head)
            return
        if not db.share_valid(share):
            self._respond_html(410, render("expired.html", **ctx), head)
            return
        photo = db.get_photo(self._db(), _rget(share, "photo_id"))
        if photo is None or _rget(photo, "missing", 0):
            self._respond_html(404, render("expired.html", **ctx), head)
            return

        sha1 = str(_rget(photo, "sha1", ""))
        tq = quote(token, safe="")
        image_url = f"/media/display/{sha1}.jpg?t={tq}"
        expires_at = _rget(share, "expires_at")
        if expires_at:
            when = _fmt_local_date(expires_at) or str(expires_at)
            expiry_line = f"Link expires {when}"
        else:
            expiry_line = "Permanent link"
        doc = render(
            "share.html",
            image_url=html_escape(image_url),
            display_url=html_escape(image_url),
            download_url=html_escape(f"/media/orig/{sha1}?t={tq}"),
            filename=html_escape(str(_rget(photo, "filename", ""))),
            taken_line=html_escape(_fmt_date(_rget(photo, "taken_at"))),
            expiry_line=html_escape(expiry_line),
            **ctx,
        )
        self._respond_html(200, doc, head)

    def _page_admin(self, head: bool) -> None:
        if not is_admin(self):
            if config.ADMIN_TOKEN:            # login is possible → send them there
                self._redirect("/admin/login")
            else:
                self._respond_html(403, _403_HTML, head)
            return
        self._respond_html(200, render("admin.html", **self._base_ctx()), head)

    # ── admin login / logout (public hosting) ─────────────────────────────

    def _page_login(self, head: bool, err: str = "") -> None:
        if is_admin(self):
            self._redirect("/admin")
            return
        if not config.ADMIN_TOKEN:
            self._respond_html(403, _403_HTML, head)
            return
        self._respond_html(200, _LOGIN_HTML.replace("{err}", html_escape(err)), head)

    def _do_login(self) -> None:
        if not config.ADMIN_TOKEN:
            self._respond_html(403, _403_HTML)
            return
        ip = self.client_address[0]
        if _login_throttled(ip):
            self._respond_html(429, _LOGIN_HTML.replace(
                "{err}", "Too many attempts — try again later."))
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        if length <= 0 or length > 4096:
            self._page_login(False, "Enter the access token.")
            return
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        token = (parse_qs(raw).get("token") or [""])[0]
        if not token or not hmac.compare_digest(token, config.ADMIN_TOKEN):
            _login_record_failure(ip)
            self._page_login(False, "Wrong token.")
            return
        secure = "; Secure" if config.BASE_URL.startswith("https://") else ""
        self._redirect("/admin", extra_headers=[(
            "Set-Cookie",
            f"adm={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000{secure}",
        )])

    def _do_logout(self) -> None:
        self._redirect("/", extra_headers=[(
            "Set-Cookie", "adm=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0",
        )])

    def _redirect(self, location: str,
                  extra_headers: list[tuple[str, str]] | None = None) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        for k, v in (extra_headers or []):
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    # ── JSON API ──────────────────────────────────────────────────────────

    def _admin_gate_json(self) -> bool:
        if is_admin(self):
            return True
        self._respond_json(403, {"error": "forbidden"})
        return False

    def _api_healthz(self) -> None:
        try:
            with closing(_conn()) as conn:
                n = conn.execute(
                    "SELECT COUNT(*) FROM photos WHERE missing=0"
                ).fetchone()[0]
        except sqlite3.Error:
            n = 0
        self._respond_json(200, {"ok": True, "photos": n})

    def _api_state(self) -> None:
        artwork: dict[str, int] = {}
        with closing(_conn()) as conn:
            for folder, n in conn.execute(
                "SELECT folder, COALESCE(SUM(is_artwork),0) FROM photos "
                "WHERE missing=0 GROUP BY folder"
            ).fetchall():
                artwork[folder] = int(n)
        folders = [
            {
                "folder": str(_rget(f, "folder", "")),
                "total": int(_rget(f, "total", 0) or 0),
                "public": int(_rget(f, "public", 0) or 0),
                "artwork": artwork.get(str(_rget(f, "folder", "")), 0),
                "cover_sha1": _rget(f, "cover_sha1"),
            }
            for f in db.all_folders(self._db())
        ]
        self._respond_json(200, {"folders": folders, "shares": len(db.list_shares(self._db()))})

    def _api_photos(self, query: dict) -> None:
        folder = _nfc((query.get("folder") or [""])[0])
        sql = (
            "SELECT id, sha1, filename, kind, visibility, is_artwork, "
            "taken_at, width, height FROM photos WHERE missing=0"
        )
        params: list = []
        if folder and folder not in ("*", "All"):
            sql += " AND folder=?"
            params.append(folder)
        sql += " ORDER BY taken_at IS NULL, taken_at, id"
        with closing(_conn()) as conn:
            rows = conn.execute(sql, params).fetchall()
        photos = [
            {
                "id": r["id"],
                "sha1": r["sha1"],
                "filename": r["filename"],
                "kind": r["kind"],
                "visibility": r["visibility"],
                "is_artwork": int(r["is_artwork"] or 0),
                "taken_at": r["taken_at"],
                "width": r["width"],
                "height": r["height"],
            }
            for r in rows
        ]
        self._respond_json(200, {"photos": photos})

    def _api_visibility(self, body: dict) -> None:
        vis = body.get("visibility")
        if vis not in ("public", "private"):
            self._respond_json(400, {"error": "visibility must be 'public' or 'private'"})
            return
        ids = body.get("ids")
        folder = body.get("folder")
        if ids is not None and folder is not None:
            self._respond_json(400, {"error": "provide ids OR folder, not both"})
            return
        if ids is not None:
            if not _valid_ids(ids):
                self._respond_json(400, {"error": "ids must be a non-empty list of ints"})
                return
            ret = db.set_visibility(self._db(), vis, ids=ids)
            changed = ret if isinstance(ret, int) else len(ids)
        elif isinstance(folder, str) and folder.strip():
            folder = _nfc(folder.strip())
            ret = db.set_visibility(self._db(), vis, folder=folder)
            if isinstance(ret, int):
                changed = ret
            else:
                with closing(_conn()) as conn:
                    changed = conn.execute(
                        "SELECT COUNT(*) FROM photos WHERE folder=? AND missing=0",
                        (folder,),
                    ).fetchone()[0]
        else:
            self._respond_json(400, {"error": "missing ids or folder"})
            return
        self._respond_json(200, {"ok": True, "changed": changed})

    def _api_artwork(self, body: dict) -> None:
        ids = body.get("ids")
        artwork = body.get("artwork")
        if not _valid_ids(ids):
            self._respond_json(400, {"error": "ids must be a non-empty list of ints"})
            return
        if not isinstance(artwork, bool):
            self._respond_json(400, {"error": "artwork must be true or false"})
            return
        ret = db.set_artwork(self._db(), ids, artwork)
        changed = ret if isinstance(ret, int) else len(ids)
        self._respond_json(200, {"ok": True, "changed": changed})

    def _api_share_create(self, body: dict) -> None:
        photo_id = body.get("photo_id")
        if not isinstance(photo_id, int) or isinstance(photo_id, bool):
            self._respond_json(400, {"error": "photo_id must be an int"})
            return
        if db.get_photo(self._db(), photo_id) is None:
            self._respond_json(404, {"error": "photo not found"})
            return

        expires = body.get("expires", "never")
        if not isinstance(expires, str):
            self._respond_json(400, {"error": "invalid expires"})
            return
        if expires in EXPIRES_HOURS:
            expires_at = (
                _now_utc() + timedelta(hours=EXPIRES_HOURS[expires])
            ).isoformat(timespec="seconds")
        elif expires == "never":
            expires_at = None
        elif DATE_RE.match(expires):
            try:
                d = datetime.strptime(expires, "%Y-%m-%d")
            except ValueError:
                self._respond_json(400, {"error": "invalid custom date"})
                return
            expires_at = datetime(
                d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc
            ).isoformat(timespec="seconds")
        else:
            self._respond_json(
                400, {"error": "expires must be 24h|7d|30d|never|YYYY-MM-DD"}
            )
            return

        note = body.get("note")
        if note is not None:
            if not isinstance(note, str):
                self._respond_json(400, {"error": "note must be a string"})
                return
            note = note.strip()[:500] or None

        ret = db.create_share(self._db(), photo_id, expires_at, note)
        token = ret if isinstance(ret, str) else _rget(ret, "token")
        if not token:
            self._respond_json(500, {"error": "share creation failed"})
            return
        self._respond_json(200, {
            "ok": True,
            "url": config.BASE_URL + "/s/" + token,
            "token": token,
            "expires_at": expires_at,
        })

    def _api_share_revoke(self, body: dict) -> None:
        token = body.get("token")
        if not isinstance(token, str) or not token:
            self._respond_json(400, {"error": "missing token"})
            return
        if db.get_share(self._db(), token) is None:
            self._respond_json(404, {"error": "unknown token"})
            return
        db.revoke_share(self._db(), token)
        self._respond_json(200, {"ok": True})

    def _api_shares(self) -> None:
        now = _now_utc()
        items = []
        for r in db.list_shares(self._db()):
            token = str(_rget(r, "token", ""))
            expires_at = _rget(r, "expires_at")
            revoked = bool(_rget(r, "revoked", 0))
            exp_dt = _parse_iso(expires_at)
            items.append({
                "token": token,
                "url": config.BASE_URL + "/s/" + token,
                "photo_id": _rget(r, "photo_id"),
                "sha1": _rget(r, "sha1"),
                "filename": _rget(r, "filename"),
                "created_at": _rget(r, "created_at"),
                "expires_at": expires_at,
                "revoked": revoked,
                "expired": bool(exp_dt is not None and exp_dt <= now),
                "note": _rget(r, "note"),
            })
        self._respond_json(200, {"shares": items})

    # ── response + body helpers ───────────────────────────────────────────

    def _read_json_body(self) -> dict | None:
        """Parse the POST body as a JSON object; respond 400 + None on any problem."""
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = -1
        if length <= 0 or length > MAX_BODY:
            self._respond_json(400, {"error": "missing or oversized body"})
            return None
        try:
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            body = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._respond_json(400, {"error": "invalid json"})
            return None
        if not isinstance(body, dict):
            self._respond_json(400, {"error": "body must be a json object"})
            return None
        return body

    def _respond_json(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command == "HEAD":
            return
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _respond_html(self, status: int, doc: str, head: bool = False) -> None:
        data = doc.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if head or self.command == "HEAD":
            return
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


# ─── module-level builders ─────────────────────────────────────────────────


def _build_collage_tiles() -> str:
    """Landing collage: up to 14 public photos, newest artwork first."""
    try:
        with closing(_conn()) as conn:
            rows = conn.execute(
                # GROUP BY sha1: content living in several folders tiles once.
                "SELECT sha1, width, height, MAX(is_artwork) AS art, "
                "       MAX(COALESCE(taken_at,'')) AS taken "
                "FROM photos WHERE visibility='public' AND missing=0 "
                "GROUP BY sha1 "
                "ORDER BY art DESC, taken DESC, MAX(id) DESC "
                "LIMIT ?",
                (COLLAGE_CAP,),
            ).fetchall()
    except sqlite3.Error:
        return ""  # DB not indexed yet: landing renders with an empty collage
    parts: list[str] = []
    for i, r in enumerate(rows, start=1):
        sha1 = r["sha1"]
        if not SHA1_RE.match(sha1 or ""):
            continue
        w, h = r["width"], r["height"]
        dims = f' width="{int(w)}" height="{int(h)}"' if w and h else ""
        loading = "eager" if i <= 4 else "lazy"
        parts.append(
            f'<figure class="tile tile--{i}" data-speed="{TILE_SPEEDS[(i - 1) % len(TILE_SPEEDS)]}">'
            f'<img src="/media/thumb/{sha1}.jpg" alt=""{dims} loading="{loading}">'
            "</figure>"
        )
    return "\n".join(parts)


def _disposition(filename: str, sha1: str) -> str:
    """RFC 6266 Content-Disposition with an ASCII fallback name."""
    ascii_name = "".join(
        c for c in filename.encode("ascii", "ignore").decode() if c not in '"\r\n'
    ) or f"{sha1}.bin"
    header = f'attachment; filename="{ascii_name}"'
    if ascii_name != filename:
        header += f"; filename*=UTF-8''{quote(filename)}"
    return header


def _valid_ids(ids) -> bool:
    return (
        isinstance(ids, list)
        and bool(ids)
        and all(isinstance(i, int) and not isinstance(i, bool) for i in ids)
    )


_403_HTML = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    "<title>403 — HARV BALU</title><style>"
    "body{margin:0;min-height:100vh;display:grid;place-items:center;"
    "background:#F2EFE9;color:#0B0B0A;font-family:system-ui,sans-serif}"
    "h1{font-size:4rem;margin:0 0 .5rem}</style></head><body><div>"
    "<h1>403</h1><p>Admin only.</p></div></body></html>"
)


# ─── server bootstrap ──────────────────────────────────────────────────────


class _ReusableServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    print("================================================", file=sys.stderr, flush=True)
    print(f" {config.SITE_NAME} — Portfolio", file=sys.stderr, flush=True)
    print(f" URL:    http://{config.HOST}:{config.PORT}/", file=sys.stderr, flush=True)
    print(f" Admin:  http://{config.HOST}:{config.PORT}/admin", file=sys.stderr, flush=True)
    print(f" DB:     {config.DB_PATH}", file=sys.stderr, flush=True)
    print(f" Photos: {config.PHOTO_MOUNT}", file=sys.stderr, flush=True)
    print("================================================", file=sys.stderr, flush=True)
    server = _ReusableServer((config.HOST, config.PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[portfolio] stopped", file=sys.stderr, flush=True)
        server.server_close()


if __name__ == "__main__":
    main()

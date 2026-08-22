#!/usr/bin/env python3
"""Export the public portfolio as a static site for Vercel.

The live app (``portfolio_app.server``) is a Python server that reads the
originals off the ``/Volumes/photo`` NAS share and gates every image behind a
visibility check. Vercel can run neither the server nor reach the NAS, so this
script renders the three *public* routes ahead of time and rewrites every image
URL to point at a public host (WordPress, by default).

What survives the export
    /            landing (collage + collection cards + about)
    /work        the collection index
    /c/<slug>    one page per public collection
    /404.html

What does NOT survive, by design
    /admin/*     the admin panel — there is no server to authenticate against
    /s/<token>   expiring share links — token validation is inherently dynamic
    /media/orig  originals are never published; they stay on the NAS

Pages are rendered through the *same* templates and the *same* DB queries the
live server uses, then two rewrites are applied to the finished HTML:

    /media/thumb/<sha1>.jpg    →  <IMAGE_BASE>/<sha1>-t.jpg
    /media/display/<sha1>.jpg  →  <IMAGE_BASE>/<sha1>-d.jpg
    /c/<url-encoded folder>    →  /c/<ascii-slug>

Rewriting the finished HTML (rather than re-implementing the markup) is what
keeps this exporter honest: the static pages are byte-identical to the served
ones apart from those URLs.

Usage
    python3 export_static.py                 # → dist/
    python3 export_static.py --out /tmp/site
    PORTFOLIO_IMAGE_BASE=https://cdn.example.com/photos python3 export_static.py

The image host is a single value. Moving off WordPress later means re-running
this with a different ``--image-base``; nothing else changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import unicodedata
from contextlib import closing
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from portfolio_app import config, db  # noqa: E402
from portfolio_app.render import render, html_escape  # noqa: E402
from portfolio_app.server import (  # noqa: E402
    COLLAGE_CAP,
    SHA1_RE,
    TILE_SPEEDS,
    _404_HTML,
    _rget,
)

DEFAULT_IMAGE_BASE = "https://harvinder.dscloud.me/blog/wp-content/uploads/portfolio"

# Folders excluded from the STATIC site only (Harv, 2026-08-05: camera work
# only for now — "we'll come back to this"). The DB and the private server are
# untouched: his admin-panel curation stays exactly as he left it, and a photo
# whose content also lives in a camera folder still appears through that row.
EXCLUDED_FOLDERS = {"AI Generated"}

# About copy for the camera-only edition (the server's ABOUT_HTML mentions
# AI-generated art, which this build deliberately does not show).
ABOUT_HTML_STATIC = (
    "<p>BAY AREA PHOTOGRAPHER CHASING LIGHT ACROSS LANDSCAPES, WILDLIFE, "
    "COSMOLOGY, AND TRAVEL. FROM THE PACIFIC COAST TO THE NIGHT SKY — "
    "SHOT SLOWLY, EDITED QUIETLY, SHARED RARELY.</p>"
)

ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
         "XI", "XII", "XIII", "XIV", "XV")


def roman(n: int) -> str:
    return ROMAN[n - 1] if 1 <= n <= len(ROMAN) else str(n)


MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def epoch_label(first_iso: str, last_iso: str) -> str:
    """'2003 — 2022' for a span, 'Feb 2023' for one month, '2022' for one year."""
    fy, fm = first_iso[:4], first_iso[5:7]
    ly, lm = last_iso[:4], last_iso[5:7]
    if fy != ly:
        return f"{fy} — {ly}"
    if fm != lm:
        return fy
    try:
        return f"{MONTHS[int(fm) - 1]} {fy}"
    except (ValueError, IndexError):
        return fy

# /media/<kind>/<sha1>.jpg  — the only image URL shape the templates emit.
MEDIA_RE = re.compile(r"/media/(thumb|display)/([0-9a-f]{40})\.jpg")
SUFFIX = {"thumb": "-t.jpg", "display": "-d.jpg"}


# ── helpers ────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Folder name → ASCII URL slug ('Cancún' → 'cancun').

    Collection directories are written to disk under this name, so it must be
    ASCII: a literal 'Cancún' directory round-trips through NFC/NFD and percent
    encoding differently on macOS, Git, and Vercel's CDN, and one of those three
    always gets it wrong.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    return slug or "collection"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def base_ctx() -> dict:
    """Mirrors server._base_ctx()."""
    return {
        "site_name": html_escape(config.SITE_NAME),
        "hero_name": html_escape(config.SITE_NAME),
        "contact_email": html_escape(config.CONTACT_EMAIL),
        "instagram_url": html_escape(config.INSTAGRAM_URL),
        "year": datetime.now().year,
    }


# ── markup builders (ports of the server's handler methods) ────────────────

def build_collection_cards(conn) -> tuple[str, int, int, list[dict], set[tuple[str, str]]]:
    """Mirrors server._build_collection_cards(), plus the folder list and the
    (sha1, kind) pairs the cards depend on (for bundling)."""
    cards: list[str] = []
    folders: list[dict] = []
    critical: set[tuple[str, str]] = set()
    index = 0
    total_public = 0
    for f in db.all_folders(conn):
        public = int(_rget(f, "public", 0) or 0)
        if public <= 0 or str(_rget(f, "folder", "")) in EXCLUDED_FOLDERS:
            continue
        index += 1
        total_public += public
        name = str(_rget(f, "folder", ""))
        cover = str(_rget(f, "cover_sha1", "") or "")
        if SHA1_RE.match(cover):
            critical.add((cover, "display"))
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
        folders.append({"folder": name, "slug": slugify(name), "public": public,
                        "cover": cover if SHA1_RE.match(cover) else ""})
    return "\n".join(cards), index, total_public, folders, critical


def build_collage_tiles(conn) -> tuple[str, set[tuple[str, str]]]:
    """Mirrors server._build_collage_tiles(); also returns its (sha1, kind) deps.

    Camera edition: excluded folders don't feed the collage, and the artwork
    flag is ignored for ordering — every artwork-flagged photo is AI, so with
    AI excluded the plates are simply the newest camera observations.
    """
    marks = ",".join("?" * len(EXCLUDED_FOLDERS))
    rows = conn.execute(
        "SELECT sha1, width, height, "
        "       MAX(COALESCE(taken_at,'')) AS taken "
        f"FROM photos WHERE visibility='public' AND missing=0 "
        f"AND folder NOT IN ({marks}) "
        "GROUP BY sha1 "
        "ORDER BY taken DESC, MAX(id) DESC "
        "LIMIT ?",
        (*EXCLUDED_FOLDERS, COLLAGE_CAP),
    ).fetchall()
    parts: list[str] = []
    critical: set[tuple[str, str]] = set()
    for i, r in enumerate(rows, start=1):
        sha1 = r["sha1"]
        if not SHA1_RE.match(sha1 or ""):
            continue
        critical.add((sha1, "thumb"))
        w, h = r["width"], r["height"]
        dims = f' width="{int(w)}" height="{int(h)}"' if w and h else ""
        loading = "eager" if i <= 4 else "lazy"
        parts.append(
            f'<figure class="tile tile--{i}" data-speed="{TILE_SPEEDS[(i - 1) % len(TILE_SPEEDS)]}">'
            f'<img src="/media/thumb/{sha1}.jpg" alt=""{dims} loading="{loading}">'
            "</figure>"
        )
    return "\n".join(parts), critical


def collection_epochs(conn) -> dict[str, dict]:
    """Per-collection observation facts: count, first/last ISO date, label."""
    marks = ",".join("?" * len(EXCLUDED_FOLDERS))
    rows = conn.execute(
        "SELECT folder, COUNT(*) AS n, "
        "       MIN(substr(taken_at,1,10)) AS first_obs, "
        "       MAX(substr(taken_at,1,10)) AS last_obs "
        f"FROM photos WHERE visibility='public' AND missing=0 "
        f"AND folder NOT IN ({marks}) "
        "GROUP BY folder",
        (*EXCLUDED_FOLDERS,),
    ).fetchall()
    out: dict[str, dict] = {}
    for r in rows:
        first = str(r["first_obs"] or "")
        last = str(r["last_obs"] or "")
        out[str(r["folder"])] = {
            "n": int(r["n"]),
            "first": first,
            "last": last,
            "label": epoch_label(first, last) if first and last else "",
        }
    return out


def build_meridian_stations(folders: list[dict], epochs: dict[str, dict],
                            covers: dict[str, str]) -> tuple[str, str]:
    """The Meridian: collections as survey stations, newest last-observation
    first, descending into the earliest epoch. Returns (markup, survey_span).

    Craft note: the station reads name-first — the designation and epoch are a
    data line BELOW the name, never an eyebrow above it.
    """
    stations = sorted(
        folders,
        key=lambda f: epochs.get(f["folder"], {}).get("last", ""),
        reverse=True,
    )
    parts: list[str] = []
    for i, f in enumerate(stations, start=1):
        name = f["folder"]
        ep = epochs.get(name, {})
        cover = covers.get(name, "")
        img = (
            f'<img class="station-plate" src="/media/display/{cover}.jpg" '
            f'alt="" loading="{"eager" if i == 1 else "lazy"}">'
        ) if SHA1_RE.match(cover) else ""
        parts.append(
            f'<li class="station">'
            f'<span class="station-tick" aria-hidden="true"></span>'
            f'<a class="station-link" href="/c/{f["slug"]}">'
            f'{img}'
            f'<span class="station-text">'
            f'<span class="station-name">{html_escape(name)}</span>'
            f'<span class="station-data">Chart {roman(i)} · '
            f'{ep.get("n", 0)} frames · {html_escape(ep.get("label", ""))}</span>'
            f'</span>'
            f'</a></li>'
        )
    years = [e["first"][:4] for e in epochs.values() if e.get("first")] + \
            [e["last"][:4] for e in epochs.values() if e.get("last")]
    span = f"{min(years)} — {max(years)}" if years else ""
    return "\n".join(parts), span


def build_collection_tiles(conn, folder: str) -> tuple[str, int]:
    """Mirrors server._page_collection()'s tile loop."""
    tiles: list[str] = []
    seen: set[str] = set()
    for p in db.public_photos(conn, folder=folder):
        sha1 = str(_rget(p, "sha1", ""))
        if not SHA1_RE.match(sha1) or sha1 in seen:
            continue
        seen.add(sha1)
        taken = html_escape(str(_rget(p, "taken_at", "") or ""))
        kind = html_escape(str(_rget(p, "kind", "image")))
        w, h = _rget(p, "width"), _rget(p, "height")
        dims = f' width="{int(w)}" height="{int(h)}"' if w and h else ""
        loading = "eager" if len(seen) <= 4 else "lazy"  # first frames paint now
        tiles.append(
            f'<a class="ph" data-sha1="{sha1}" '
            f'data-taken="{taken}" data-kind="{kind}" '
            f'href="/media/display/{sha1}.jpg">'
            f'<img src="/media/thumb/{sha1}.jpg" alt=""{dims} '
            f'loading="{loading}"></a>'
        )
    return "\n".join(tiles), len(tiles)


# ── URL rewriting ──────────────────────────────────────────────────────────

def rewrite(html: str, image_base: str, slug_by_href: dict[str, str],
            needed: set[tuple[str, str]],
            bundled: set[tuple[str, str]]) -> str:
    """Point image URLs at their host and collection links at ASCII slugs.

    Images in ``bundled`` resolve to ``/img/…`` — files that ship inside the
    deploy itself, so the pages built from them (landing, /work) render even
    when the home-hosted WordPress is offline. Everything else points at
    ``image_base``. Every match is recorded in ``needed`` so the caller knows
    exactly which derivative files must exist on the image host.
    """
    def _img(m: re.Match) -> str:
        kind, sha1 = m.group(1), m.group(2)
        needed.add((sha1, kind))
        if (sha1, kind) in bundled:
            return f"/img/{sha1}{SUFFIX[kind]}"
        return f"{image_base}/{sha1}{SUFFIX[kind]}"

    html = MEDIA_RE.sub(_img, html)
    for encoded_href, slug in slug_by_href.items():
        html = html.replace(f'href="{encoded_href}"', f'href="/c/{slug}"')
    return html


# ── export ─────────────────────────────────────────────────────────────────

# Paths this exporter owns. Everything else in the output directory is left
# alone — once it becomes the deploy repo it also holds .git, and blowing that
# away on every rebuild would be a very annoying way to lose the remote.
MANAGED = ("index.html", "404.html", "vercel.json", "work", "c", "static", "img")

# Build metadata lives outside dist/: dist/ is exactly what gets deployed, and
# the manifest is a build artifact for publish_images.py, not a public page.
MANIFEST_PATH = ROOT / "build" / "manifest.json"

VERCEL_CONFIG = {
    "$schema": "https://openapi.vercel.sh/vercel.json",
    "cleanUrls": True,
    "trailingSlash": False,
    "headers": [
        {
            "source": "/static/(.*)",
            "headers": [
                {"key": "Cache-Control", "value": "public, max-age=3600, must-revalidate"},
            ],
        },
        {
            # sha1-addressed: a changed image is a different URL, so immutable.
            "source": "/img/(.*)",
            "headers": [
                {"key": "Cache-Control", "value": "public, max-age=31536000, immutable"},
            ],
        },
        {
            "source": "/(.*)",
            "headers": [
                {"key": "X-Content-Type-Options", "value": "nosniff"},
                {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"},
                {"key": "X-Frame-Options", "value": "SAMEORIGIN"},
            ],
        },
    ],
}


def _clean(out_dir: Path) -> None:
    """Remove only the generated paths, preserving .git and anything hand-added."""
    for name in MANAGED:
        target = out_dir / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


def export(out_dir: Path, image_base: str) -> dict:
    image_base = image_base.rstrip("/")
    needed: set[tuple[str, str]] = set()

    out_dir.mkdir(parents=True, exist_ok=True)
    _clean(out_dir)

    with closing(_conn()) as conn:
        cards, n_collections, n_public, folders, card_deps = build_collection_cards(conn)
        collage, collage_deps = build_collage_tiles(conn)

        # ── bundle the landing-critical images into the deploy itself ──────
        # The Synology WordPress is home-hosted (~90% uptime, Harv's estimate).
        # The first thing any visitor sees must not depend on it: the collage
        # tiles and collection covers are copied into dist/img/ and served by
        # Vercel. Collection-page grids (the other ~860 files) stay on
        # WordPress. A file whose derivative is missing on the NAS falls back
        # to the WordPress URL rather than shipping a broken landing page.
        bundled: set[tuple[str, str]] = set()
        img_dir = out_dir / "img"
        img_dir.mkdir(parents=True, exist_ok=True)
        src_for = {"thumb": config.thumb_path, "display": config.display_path}
        # The Instrument's photograph is landing-critical too: the overture on
        # /work ends on it, and the overture must not depend on the NAS.
        instrument_deps = {(config.INSTRUMENT_PHOTO_SHA1, "display")}
        for sha1, kind in sorted(card_deps | collage_deps | instrument_deps):
            src = src_for[kind](sha1)
            if src.is_file():
                shutil.copy2(src, img_dir / f"{sha1}{SUFFIX[kind]}")
                bundled.add((sha1, kind))
            else:
                print(f"WARN: {kind}/{sha1} not on NAS — falling back to image host",
                      file=sys.stderr)

        # href as it appears in the freshly rendered markup → ascii slug
        slug_by_href = {
            html_escape("/c/" + quote(f["folder"], safe="")): f["slug"] for f in folders
        }

        epochs = collection_epochs(conn)
        covers = {f["folder"]: f["cover"] for f in folders}
        meridian, survey_span = build_meridian_stations(folders, epochs, covers)

        # Chart numbers follow the meridian's order (newest last-observation
        # first) so a collection page's designation matches its station.
        station_order = sorted(
            folders,
            key=lambda f: epochs.get(f["folder"], {}).get("last", ""),
            reverse=True,
        )
        chart_no = {f["folder"]: roman(i)
                    for i, f in enumerate(station_order, start=1)}

        pages: list[tuple[Path, str]] = []

        pages.append((out_dir / "index.html", render(
            "index.html",
            collage_tiles=collage,
            collection_cards=cards,
            collection_count=n_collections,
            photo_total=n_public,
            about_html=ABOUT_HTML_STATIC,
            **base_ctx(),
        )))

        pages.append((out_dir / "work" / "index.html", render(
            "work.html",
            meridian_stations=meridian,
            survey_span=html_escape(survey_span),
            collection_count=n_collections,
            photo_total=n_public,
            instrument_photo=f"/media/display/{config.INSTRUMENT_PHOTO_SHA1}.jpg",
            instrument_epoch=html_escape(config.INSTRUMENT_PHOTO_EPOCH),
            **base_ctx(),
        )))

        for f in folders:
            tiles, count = build_collection_tiles(conn, f["folder"])
            if not count:
                continue
            ep = epochs.get(f["folder"], {})
            pages.append((out_dir / "c" / f["slug"] / "index.html", render(
                "collection.html",
                folder_name=html_escape(f["folder"]),
                collection_name=html_escape(f["folder"]),
                count=count,
                photo_count=count,
                chart_no=chart_no.get(f["folder"], ""),
                epoch_range=html_escape(ep.get("label", "")),
                photo_tiles=tiles,
                **base_ctx(),
            )))

    pages.append((out_dir / "404.html", _404_HTML))

    for path, html in pages:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            rewrite(html, image_base, slug_by_href, needed, bundled),
            encoding="utf-8")

    # Static assets: the public site needs these four only. admin.css/admin.js
    # belong to the admin panel, which is not exported. Asset URLs in the HTML
    # get a content-hash query (?v=abc123) so a redeploy can never pair new
    # pages with an hour-stale cached stylesheet (vercel.json caches /static/).
    static_out = out_dir / "static"
    static_out.mkdir(parents=True, exist_ok=True)
    versions: dict[str, str] = {}
    for name in ("style.css", "landing.css", "app.js", "instrument.js"):
        src = ROOT / "static" / name
        shutil.copy2(src, static_out / name)
        versions[name] = hashlib.sha1(src.read_bytes()).hexdigest()[:10]

    for page_path in out_dir.rglob("*.html"):
        html = page_path.read_text(encoding="utf-8")
        for name, v in versions.items():
            html = html.replace(f"/static/{name}", f"/static/{name}?v={v}")
        page_path.write_text(html, encoding="utf-8")

    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "image_base": image_base,
        "collections": folders,
        "public_photos": n_public,
        "derivatives": [
            {"sha1": s, "kind": k, "filename": f"{s}{SUFFIX[k]}"}
            for s, k in sorted(needed)
        ],
        # Also published to WordPress (see publish_images.py) so a future
        # export that picks different collage/cover images never 404s.
        "bundled_in_deploy": [
            {"sha1": s, "kind": k, "filename": f"{s}{SUFFIX[k]}"}
            for s, k in sorted(bundled)
        ],
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "vercel.json").write_text(
        json.dumps(VERCEL_CONFIG, indent=2), encoding="utf-8")

    return {
        "pages": len(pages),
        "collections": len(folders),
        "public_photos": n_public,
        "derivatives": len(needed),
        "bundled": len(bundled),
        "out": out_dir,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "dist"), help="output directory")
    ap.add_argument("--image-base",
                    default=os.environ.get("PORTFOLIO_IMAGE_BASE", DEFAULT_IMAGE_BASE),
                    help="public base URL that serves <sha1>-t.jpg / <sha1>-d.jpg")
    args = ap.parse_args()

    if not config.DB_PATH.exists():
        print(f"ERROR: no database at {config.DB_PATH}", file=sys.stderr)
        return 1

    stats = export(Path(args.out).resolve(), args.image_base)
    print(f"exported {stats['pages']} pages "
          f"({stats['collections']} collections, {stats['public_photos']} public photos)")
    print(f"bundled {stats['bundled']} landing-critical images into dist/img/")
    print(f"needs {stats['derivatives']} derivative files on {args.image_base}")
    print(f"→ {stats['out']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

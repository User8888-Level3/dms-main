#!/usr/bin/env python3
"""Export the static site even when the NAS share is not mounted.

``export_static.py`` bundles the landing-critical derivatives (collage
thumbs, collection covers, the Instrument's photograph) into ``dist/img/`` by
copying them off ``/Volumes/photo/.portfolio``. That share is home-hosted and
refuses to mount often enough (AppleScript -5014, stale stubs) that a build
would silently fall back to WordPress URLs — and the front door would then
depend on the home server, which is exactly what bundling exists to prevent.

This wrapper keeps the exporter honest without the mount:

  1. stage every derivative already shipped in the deploy repo
     (``~/Sites/harv-portfolio/img/<sha1>-t.jpg`` / ``-d.jpg``) into a
     temporary directory laid out like the NAS
     (``.portfolio/{thumb,display}/<aa>/<sha1>.jpg``);
  2. fetch anything else the exporter will need from the public image host
     (the same WordPress path the collection grids embed from);
  3. rebind ``config.THUMB_DIR`` / ``config.DISPLAY_DIR`` to the stage (they are
     read-at-call module globals) and run the exporter.

If the real share IS mounted and populated, it is used as-is and the stage is
only a fallback for files missing there.

Usage
    python3 stage_and_export.py                  # → dist/
    python3 stage_and_export.py --out /tmp/site
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from portfolio_app import config  # noqa: E402
import export_static  # noqa: E402

DEPLOY_IMG = Path.home() / "Sites" / "harv-portfolio" / "img"
STAGE = ROOT / "build" / "deriv-stage" / ".portfolio"
NAME_RE = re.compile(r"^([0-9a-f]{40})-(t|d)\.jpg$")
KIND = {"t": "thumb", "d": "display"}


def stage_from_deploy() -> int:
    n = 0
    if not DEPLOY_IMG.is_dir():
        return 0
    for f in DEPLOY_IMG.iterdir():
        m = NAME_RE.match(f.name)
        if not m:
            continue
        sha1, k = m.group(1), KIND[m.group(2)]
        dst = STAGE / k / sha1[:2] / f"{sha1}.jpg"
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        n += 1
    return n


def fetch(sha1: str, kind: str, image_base: str) -> bool:
    dst = STAGE / kind / sha1[:2] / f"{sha1}.jpg"
    if dst.exists():
        return True
    suffix = export_static.SUFFIX[kind]
    url = f"{image_base.rstrip('/')}/{sha1}{suffix}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = r.read()
    except Exception as exc:  # noqa: BLE001 — report and move on
        print(f"WARN: could not fetch {url}: {exc}", file=sys.stderr)
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    return True


def needed_derivatives() -> set[tuple[str, str]]:
    """Exactly the (sha1, kind) pairs export_static will try to bundle."""
    import sqlite3
    from contextlib import closing
    with closing(export_static._conn()) as conn:  # noqa: SLF001
        _, _, _, _, card_deps = export_static.build_collection_cards(conn)
        _, collage_deps = export_static.build_collage_tiles(conn)
    return card_deps | collage_deps | {(config.INSTRUMENT_PHOTO_SHA1, "display")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--image-base", default=export_static.DEFAULT_IMAGE_BASE)
    args = ap.parse_args()

    real_ok = config.THUMB_DIR.is_dir() and config.DISPLAY_DIR.is_dir()
    print(f"NAS derivatives {'available' if real_ok else 'NOT mounted'} at {config.DERIV_ROOT}")

    staged = stage_from_deploy()
    print(f"staged {staged} new derivative(s) from {DEPLOY_IMG}")

    missing = 0
    for sha1, kind in sorted(needed_derivatives()):
        real = (config.THUMB_DIR if kind == "thumb" else config.DISPLAY_DIR) / sha1[:2] / f"{sha1}.jpg"
        if real_ok and real.is_file():
            continue
        if not fetch(sha1, kind, args.image_base):
            missing += 1
    if missing:
        print(f"WARN: {missing} derivative(s) unavailable anywhere — those will fall back to the image host",
              file=sys.stderr)

    if not real_ok:
        config.THUMB_DIR = STAGE / "thumb"
        config.DISPLAY_DIR = STAGE / "display"
    else:
        # prefer the NAS, but let the stage fill gaps by pointing at the stage
        # only for files the NAS lacks — simplest: if everything is on the NAS
        # the stage is unused; otherwise use the stage (a superset after fetch).
        all_real = all(
            ((config.THUMB_DIR if k == "thumb" else config.DISPLAY_DIR) / s[:2] / f"{s}.jpg").is_file()
            for s, k in needed_derivatives()
        )
        if not all_real:
            # copy NAS files into the stage so it is the superset, then rebind
            for s, k in needed_derivatives():
                real = (config.THUMB_DIR if k == "thumb" else config.DISPLAY_DIR) / s[:2] / f"{s}.jpg"
                dst = STAGE / k / s[:2] / f"{s}.jpg"
                if real.is_file() and not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(real, dst)
            config.THUMB_DIR = STAGE / "thumb"
            config.DISPLAY_DIR = STAGE / "display"

    stats = export_static.export(Path(args.out).resolve(), args.image_base)
    print(f"exported {stats['pages']} pages "
          f"({stats['collections']} collections, {stats['public_photos']} public photos)")
    print(f"bundled {stats['bundled']} landing-critical images into dist/img/")
    print(f"→ {stats['out']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

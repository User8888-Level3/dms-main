#!/usr/bin/env python3
"""Copy the public derivatives from the NAS to the WordPress uploads folder.

The static site (see ``export_static.py``) points every image at

    https://harvinder.dscloud.me/blog/wp-content/uploads/portfolio/<sha1>-t.jpg
    https://harvinder.dscloud.me/blog/wp-content/uploads/portfolio/<sha1>-d.jpg

This script puts those files there. It copies straight into the WordPress
uploads directory over SMB rather than going through the WP REST API, because
the REST path is rate-limited by Wordfence (~7s between uploads — nearly two
hours for 898 files) and would also register every image in the media library,
generating several extra resized copies each and burying the blog's real
attachments under a thousand portfolio JPEGs.

Files land in a plain ``portfolio/`` folder that WordPress itself never touches.

Only ``visibility='public'`` photos are ever copied: the manifest is generated
from the same query that builds the pages, so anything private is structurally
incapable of reaching this script.

Usage
    python3 publish_images.py --dry-run     # report what would happen
    python3 publish_images.py               # copy missing/changed files
    python3 publish_images.py --force       # recopy everything
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from portfolio_app import config  # noqa: E402

WP_UPLOADS = Path(
    "/Volumes/web_packages/wordpress/wp-content/uploads/portfolio"
)
MANIFEST = ROOT / "build" / "manifest.json"

SRC_DIR = {"thumb": config.THUMB_DIR, "display": config.DISPLAY_DIR}


def source_for(sha1: str, kind: str) -> Path:
    """<.portfolio>/<kind>/<sha1[:2]>/<sha1>.jpg, at wherever the share is mounted."""
    return SRC_DIR[kind] / sha1[:2] / f"{sha1}.jpg"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="report only; copy nothing")
    ap.add_argument("--force", action="store_true",
                    help="recopy even when the destination already matches")
    ap.add_argument("--manifest", default=str(MANIFEST))
    ap.add_argument("--dest", default=str(WP_UPLOADS))
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"ERROR: no manifest at {manifest_path} — run export_static.py first",
              file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest["derivatives"]

    # The NAS share must actually be mounted. config.PHOTO_MOUNT falls back to
    # the canonical path when nothing is readable, so check the resolved dir.
    if not config.DERIV_ROOT.is_dir():
        print(f"ERROR: derivatives not reachable at {config.DERIV_ROOT}\n"
              "       Mount the share:  Finder → Go → Connect to Server →\n"
              "       smb://172.22.2.147/photo",
              file=sys.stderr)
        return 1

    dest_dir = Path(args.dest)
    if not dest_dir.parent.is_dir():
        print(f"ERROR: WordPress uploads dir not reachable at {dest_dir.parent}",
              file=sys.stderr)
        return 1
    if not args.dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    copied = skipped = missing = 0
    missing_list: list[str] = []

    for i, entry in enumerate(entries, start=1):
        src = source_for(entry["sha1"], entry["kind"])
        dst = dest_dir / entry["filename"]

        if not src.is_file():
            missing += 1
            missing_list.append(f"{entry['kind']}/{entry['sha1']}")
            continue

        if not args.force and dst.is_file() and dst.stat().st_size == src.stat().st_size:
            skipped += 1
            continue

        if args.dry_run:
            copied += 1
        else:
            shutil.copy2(src, dst)
            copied += 1

        if i % 100 == 0:
            print(f"  … {i}/{len(entries)}", flush=True)

    verb = "would copy" if args.dry_run else "copied"
    print(f"\n{verb}: {copied}   already current: {skipped}   missing source: {missing}")
    print(f"destination: {dest_dir}")

    if missing:
        print(f"\n⚠ {missing} derivative(s) are not on the NAS. Regenerate them with\n"
              "  Reindex-Photos.command, then re-run this script.")
        for m in missing_list[:10]:
            print(f"    {m}")
        if len(missing_list) > 10:
            print(f"    … and {len(missing_list) - 10} more")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

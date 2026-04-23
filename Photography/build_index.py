#!/usr/bin/env python
"""Photography index CLI. Intended to be invoked by Claude, not Harv directly."""
import argparse
import signal
import threading
from pathlib import Path

from photo_index import config, db as dbmod
from photo_index.walker import walk_year_folder
from photo_index.html_out import generate_index, generate_year
from photo_index.progress import ProgressLogger
from photo_index.runner import run_indexer


def cmd_index(args) -> None:
    config.ensure_dirs()
    target = Path(args.path).resolve()
    records = list(walk_year_folder(target))
    print(f"[index] {len(records)} files under {target}")
    if args.limit:
        records = records[: args.limit]
        print(f"[index] limiting to first {args.limit}")

    stop_event = threading.Event()
    interrupts = {"n": 0}

    def _handle_sigint(signum, frame):  # noqa: ARG001
        interrupts["n"] += 1
        if interrupts["n"] == 1:
            print("\n[index] SIGINT received, draining current work... "
                  "(Ctrl+C again to force quit)", flush=True)
            stop_event.set()
        else:
            print("\n[index] second SIGINT — forcing exit.", flush=True)
            raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _handle_sigint)

    progress = ProgressLogger(
        total=len(records),
        log_path=config.LOG_DIR / "indexer.log",
        print_every=25,
    )
    stats = run_indexer(
        records=records,
        db_path=config.DB_PATH,
        thumb_root=config.THUMB_ROOT,
        workers=args.workers,
        progress_cb=progress.on_row,
        stop_event=stop_event,
    )
    progress.finish(stats)


def cmd_html(args) -> None:
    db = dbmod.open_db(config.DB_PATH)
    generate_index(db)
    years = [
        r[0]
        for r in db.execute(
            "SELECT DISTINCT year FROM files WHERE error IS NULL AND deleted_at IS NULL"
        ).fetchall()
    ]
    for y in years:
        generate_year(db, y)
    print(f"[html] wrote index + {len(years)} year pages to {config.SITE_DIR}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="build_index")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_idx = sub.add_parser("index", help="Walk a year folder and index all indexable files")
    p_idx.add_argument("path", help="Year folder, e.g. /Volumes/Pictures-Vol3/2024")
    p_idx.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only first N files (for smoke tests)",
    )
    p_idx.add_argument(
        "--workers",
        type=int,
        default=config.WORKERS,
        help=f"Worker threads (default {config.WORKERS})",
    )
    p_idx.set_defaults(fn=cmd_index)

    p_html = sub.add_parser("html", help="Regenerate site/index.html and site/years/*.html")
    p_html.set_defaults(fn=cmd_html)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

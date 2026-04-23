#!/usr/bin/env python
"""Photography index CLI. Intended to be invoked by Claude, not Harv directly."""
import argparse
import json
import signal
import threading
from pathlib import Path

from photo_index import config, db as dbmod
from photo_index.walker import walk_year_folder
from photo_index.html_out import (
    generate_index,
    generate_year,
    generate_search_json,
    generate_duplicates_html,
)
from photo_index.progress import ProgressLogger
from photo_index.runner import run_indexer
from photo_index.decide import auto_decide_all
from photo_index.apply_decisions import apply_decisions


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
    manifest = generate_search_json(db)
    total_indexed = sum(m["count"] for m in manifest)
    print(f"[html] wrote index + {len(years)} year pages + search JSON "
          f"({total_indexed} rows across {len(manifest)} years) to {config.SITE_DIR}")
    if not args.no_dups:
        stats = generate_duplicates_html(db)
        print(f"[html] duplicates.html: {stats['exact_groups']} exact groups "
              f"({stats['exact_savings']} redundant), "
              f"{stats['similar_groups']} similar groups "
              f"({stats['similar_savings']} potential)")


def _human_bytes(n: int) -> str:
    x = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if x < 1024.0:
            return f"{x:.1f} {unit}"
        x /= 1024.0
    return f"{x:.1f} PB"


def cmd_decide(args) -> None:
    db = dbmod.open_db(config.DB_PATH)
    payload = auto_decide_all(
        db,
        similar_threshold=args.similar_threshold,
        similar_max_cluster_size=args.similar_max_cluster_size,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    s = payload["summary"]
    print(f"[decide] wrote {out}")
    print(f"[decide] applied:  {s['applied_exact']} exact  +  "
          f"{s['applied_similar']} similar")
    print(f"[decide] skipped:  {s['skipped_similar_large']} similar "
          f"(cluster too big or cross-year)")
    print(f"[decide] to delete: {s['files_to_delete']} files, "
          f"reclaim {_human_bytes(s['bytes_to_reclaim'])}")


def cmd_apply(args) -> None:
    payload = json.loads(Path(args.decisions).read_text())
    result = apply_decisions(
        payload,
        db_path=config.DB_PATH,
        dry_run=not args.apply,
        run_date=args.run_date,
    )
    mode = "DRY-RUN" if result.dry_run else "APPLIED"
    print(f"[{mode}] moved={result.moved}  skipped={result.skipped}  "
          f"errors={result.errors}  bytes={_human_bytes(result.bytes_reclaimed)}")
    if result.recycle_root:
        print(f"[{mode}] recycle dir: {result.recycle_root}")


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
    p_html.add_argument(
        "--no-dups",
        action="store_true",
        help="Skip duplicates.html generation (fast path — useful during active indexing)",
    )
    p_html.set_defaults(fn=cmd_html)

    p_dec = sub.add_parser("decide", help="Auto-generate decisions.json for dup groups")
    p_dec.add_argument("--out", default="decisions.json", help="Output path")
    p_dec.add_argument("--similar-threshold", type=int, default=4)
    p_dec.add_argument("--similar-max-cluster-size", type=int, default=2)
    p_dec.set_defaults(fn=cmd_decide)

    p_app = sub.add_parser("apply", help="Apply decisions.json (default dry-run)")
    p_app.add_argument("decisions", help="Path to decisions.json")
    p_app.add_argument("--apply", action="store_true",
                       help="Actually move files (default is dry-run)")
    p_app.add_argument("--run-date", default=None,
                       help="Override dup-cleanup date suffix (YYYY-MM-DD)")
    p_app.set_defaults(fn=cmd_apply)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

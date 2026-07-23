import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
import sqlite3

from . import config
from .dups import find_exact_dups, find_similar_groups

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
)


def generate_index(db: sqlite3.Connection) -> None:
    config.ensure_dirs()
    years_rows = db.execute("""
      SELECT year, COUNT(*) as c, COALESCE(SUM(bytes),0) as b
      FROM files WHERE error IS NULL AND deleted_at IS NULL AND year IS NOT NULL
      GROUP BY year ORDER BY year DESC
    """).fetchall()
    years = []
    for year, count, year_bytes in years_rows:
        cover = db.execute("""
          SELECT thumb_rel FROM files WHERE year=? AND thumb_rel IS NOT NULL
            AND error IS NULL AND deleted_at IS NULL
          ORDER BY RANDOM() LIMIT 1
        """, (year,)).fetchone()
        thumb = f"thumbs/{cover[0]}" if cover else None
        years.append({
            "year": year,
            "count": count,
            "cover_thumb": thumb,
            "bytes_human": _human_bytes(year_bytes),
        })
    total = db.execute(
        "SELECT COUNT(*), COALESCE(SUM(bytes),0) FROM files "
        "WHERE error IS NULL AND deleted_at IS NULL"
    ).fetchone()
    total_count = total[0]
    total_bytes_human = _human_bytes(total[1])
    span = db.execute(
        "SELECT MIN(year), MAX(year) FROM files "
        "WHERE error IS NULL AND deleted_at IS NULL AND year IS NOT NULL"
    ).fetchone()
    html = _env.get_template("index.html").render(
        years=years,
        total_files=total_count,
        total_bytes_human=total_bytes_human,
        first_year=span[0],
        last_year=span[1],
    )
    (config.SITE_DIR / "index.html").write_text(html)


def generate_year(db: sqlite3.Connection, year: int) -> None:
    rows = db.execute("""
      SELECT id, sha1, thumb_rel, event_folder, kind, filename
      FROM files WHERE year=? AND error IS NULL AND deleted_at IS NULL
      ORDER BY event_folder, exif_taken_at, filename
    """, (year,)).fetchall()
    events_map: dict[str, list] = {}
    for r in rows:
        events_map.setdefault(r[3], []).append({
            "id": r[0], "sha1": r[1], "thumb_rel": r[2], "kind": r[4], "filename": r[5],
        })
    events = [{"name": name, "count": len(files), "slug": _event_slug(name), "files": files}
              for name, files in events_map.items()]
    year_bytes = db.execute(
        "SELECT COALESCE(SUM(bytes),0) FROM files WHERE year=? AND error IS NULL AND deleted_at IS NULL",
        (year,),
    ).fetchone()[0]
    html = _env.get_template("year.html").render(
        year=year,
        events=events,
        total=len(rows),
        bytes_human=_human_bytes(year_bytes),
        thumb_root="../thumbs",
    )
    out = config.SITE_DIR / "years" / f"{year}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)


def _event_slug(name: str) -> str:
    """Slugify an event-folder name for use as a URL anchor.

    Spaces and most punctuation become '-'; we keep alnum, dash, underscore.
    """
    import re
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-")
    return slug or "event"


def generate_search_json(db: sqlite3.Connection) -> list[dict]:
    """Write one site/assets/search-YYYY.json per year + a manifest.

    Returns the manifest rows (for test assertions and logging).
    Each row in search-YYYY.json is compact — the file is fetched by the browser
    search UI and held in memory, so we strip to only the fields the UI uses.
    """
    out_dir = config.SITE_DIR / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    years = [r[0] for r in db.execute(
        "SELECT DISTINCT year FROM files WHERE error IS NULL AND deleted_at IS NULL "
        "AND year IS NOT NULL ORDER BY year"
    ).fetchall()]
    manifest: list[dict] = []
    for year in years:
        rows = db.execute("""
          SELECT id, sha1, filename, event_folder, exif_taken_at, exif_camera,
                 exif_gps_lat, exif_gps_lon, kind, thumb_rel,
                 path, bytes, width, height
          FROM files
          WHERE year=? AND error IS NULL AND deleted_at IS NULL
          ORDER BY event_folder, exif_taken_at, filename
        """, (year,)).fetchall()
        data = []
        for r in rows:
            data.append({
                "id": r[0],
                "sha1": r[1],
                "f": r[2],                 # filename
                "e": r[3],                 # event_folder
                "d": r[4],                 # iso date
                "c": r[5],                 # camera
                "g": bool(r[6] is not None and r[7] is not None),
                "k": r[8],                 # kind: image|raw|video
                "t": r[9],                 # thumb_rel
                "p": r[10],                # full original path
                "b": r[11],                # bytes
                "w": r[12],                # width
                "h": r[13],                # height
            })
        out = out_dir / f"search-{year}.json"
        out.write_text(json.dumps(data, separators=(",", ":")))
        manifest.append({"year": year, "count": len(data), "file": f"assets/search-{year}.json"})
    (out_dir / "search-manifest.json").write_text(json.dumps({
        "thumb_root": "thumbs",
        "years": manifest,
    }, separators=(",", ":")))
    return manifest


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def _fetch_files_by_ids(db: sqlite3.Connection, ids: list[int]) -> list[dict]:
    # sqlite3 placeholder rewrite for IN (...) — cap batch at 500 for safety
    placeholders = ",".join("?" * len(ids))
    rows = db.execute(
        f"""
        SELECT id, path, filename, year, event_folder, bytes, mtime,
               exif_taken_at, thumb_rel, kind, sha1
        FROM files WHERE id IN ({placeholders})
        """,
        ids,
    ).fetchall()
    return [
        {
            "id": r[0], "path": r[1], "filename": r[2], "year": r[3],
            "event": r[4], "bytes": r[5] or 0, "mtime": r[6] or 0.0,
            "taken_at": r[7], "thumb_rel": r[8], "kind": r[9], "sha1": r[10],
        }
        for r in rows
    ]


def _pick_keeper(files: list[dict], strategy: str = "oldest") -> int:
    """Return file id of recommended keeper.

    oldest  — smallest mtime (first import typically)
    largest — largest file bytes (typically highest quality)
    """
    if strategy == "largest":
        key = lambda f: (-f["bytes"], f["mtime"], f["id"])
    else:  # "oldest"
        key = lambda f: (f["mtime"], -f["bytes"], f["id"])
    return sorted(files, key=key)[0]["id"]


def generate_duplicates_html(
    db: sqlite3.Connection,
    similar_threshold: int = 4,
    max_exact: int = 500,
    max_similar: int = 500,
) -> dict:
    """Render site/duplicates.html.

    Returns stats dict for logging.
    """
    config.ensure_dirs()

    exact = find_exact_dups(db)
    similar_raw = find_similar_groups(db, threshold=similar_threshold)

    # Sort by total bytes savings (descending) so biggest wins come first.
    def _hydrate_exact(g: dict) -> dict:
        files = _fetch_files_by_ids(db, g["ids"])
        savings_bytes = sum(f["bytes"] for f in files) - max(f["bytes"] for f in files)
        keeper_id = _pick_keeper(files, "oldest")
        for f in files:
            f["is_keeper"] = (f["id"] == keeper_id)
            f["bytes_human"] = _human_bytes(f["bytes"])
        return {
            "kind": "exact",
            "gid": f"e{g['ids'][0]}",
            "sha1": g["sha1"],
            "files": files,
            "count": g["count"],
            "savings_bytes": savings_bytes,
            "savings_human": _human_bytes(savings_bytes),
        }

    def _hydrate_similar(g: dict) -> dict:
        files = _fetch_files_by_ids(db, g["ids"])
        # For similar groups we conservatively estimate savings = sum of all but largest
        savings_bytes = sum(f["bytes"] for f in files) - max(f["bytes"] for f in files)
        keeper_id = _pick_keeper(files, "largest")
        for f in files:
            f["is_keeper"] = (f["id"] == keeper_id)
            f["bytes_human"] = _human_bytes(f["bytes"])
        return {
            "kind": "similar",
            "gid": f"s{g['ids'][0]}",
            "sha1": None,
            "files": files,
            "count": g["count"],
            "savings_bytes": savings_bytes,
            "savings_human": _human_bytes(savings_bytes),
        }

    exact_groups = sorted(
        (_hydrate_exact(g) for g in exact),
        key=lambda g: -g["savings_bytes"],
    )
    similar_groups = sorted(
        (_hydrate_similar(g) for g in similar_raw),
        key=lambda g: -g["savings_bytes"],
    )

    total_exact_savings = sum(g["savings_bytes"] for g in exact_groups)
    total_similar_savings = sum(g["savings_bytes"] for g in similar_groups)

    stats = {
        "exact_groups": len(exact_groups),
        "exact_files": sum(g["count"] for g in exact_groups),
        "exact_savings": _human_bytes(total_exact_savings),
        "similar_groups": len(similar_groups),
        "similar_files": sum(g["count"] for g in similar_groups),
        "similar_savings": _human_bytes(total_similar_savings),
        "similar_threshold": similar_threshold,
    }

    exact_shown = exact_groups[:max_exact]
    similar_shown = similar_groups[:max_similar]

    html = _env.get_template("duplicates.html").render(
        stats=stats,
        exact_groups=exact_shown,
        similar_groups=similar_shown,
        exact_hidden=max(0, len(exact_groups) - max_exact),
        similar_hidden=max(0, len(similar_groups) - max_similar),
    )
    (config.SITE_DIR / "duplicates.html").write_text(html)
    return stats

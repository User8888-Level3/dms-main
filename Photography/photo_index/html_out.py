import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
import sqlite3

from . import config

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
)


def generate_index(db: sqlite3.Connection) -> None:
    config.ensure_dirs()
    years_rows = db.execute("""
      SELECT year, COUNT(*) as c
      FROM files WHERE error IS NULL AND deleted_at IS NULL AND year IS NOT NULL
      GROUP BY year ORDER BY year
    """).fetchall()
    years = []
    for year, count in years_rows:
        cover = db.execute("""
          SELECT thumb_rel FROM files WHERE year=? AND thumb_rel IS NOT NULL
            AND error IS NULL AND deleted_at IS NULL
          ORDER BY RANDOM() LIMIT 1
        """, (year,)).fetchone()
        thumb = f"thumbs/{cover[0]}" if cover else None
        years.append({"year": year, "count": count, "cover_thumb": thumb})
    total = db.execute("SELECT COUNT(*) FROM files WHERE error IS NULL AND deleted_at IS NULL").fetchone()[0]
    html = _env.get_template("index.html").render(years=years, total_files=total)
    (config.SITE_DIR / "index.html").write_text(html)


def generate_year(db: sqlite3.Connection, year: int) -> None:
    rows = db.execute("""
      SELECT id, sha1, thumb_rel, event_folder, kind, filename
      FROM files WHERE year=? AND error IS NULL AND deleted_at IS NULL
      ORDER BY event_folder, exif_taken_at, filename
    """, (year,)).fetchall()
    # group by event
    events_map: dict[str, list] = {}
    for r in rows:
        events_map.setdefault(r[3], []).append({
            "id": r[0], "sha1": r[1], "thumb_rel": r[2], "kind": r[4], "filename": r[5],
        })
    events = [{"name": name, "count": len(files), "files": files}
              for name, files in events_map.items()]
    html = _env.get_template("year.html").render(
        year=year, events=events, total=len(rows), thumb_root="../thumbs")
    out = config.SITE_DIR / "years" / f"{year}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)


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
                 exif_gps_lat, exif_gps_lon, kind, thumb_rel
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
            })
        out = out_dir / f"search-{year}.json"
        out.write_text(json.dumps(data, separators=(",", ":")))
        manifest.append({"year": year, "count": len(data), "file": f"assets/search-{year}.json"})
    (out_dir / "search-manifest.json").write_text(json.dumps({
        "thumb_root": "thumbs",
        "years": manifest,
    }, separators=(",", ":")))
    return manifest

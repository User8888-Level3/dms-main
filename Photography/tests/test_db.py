from pathlib import Path
from photo_index.db import open_db, SCHEMA_VERSION

def test_open_db_creates_schema(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    assert "files" in tables
    assert "dup_groups" in tables
    assert "schema_meta" in tables
    version = conn.execute("SELECT version FROM schema_meta").fetchone()[0]
    assert version == SCHEMA_VERSION

def test_open_db_idempotent(tmp_path: Path):
    db_path = tmp_path / "test.db"
    open_db(db_path).close()
    conn = open_db(db_path)
    assert conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0

"""Threaded indexer runner.

Workers do pure decode + hash (no DB). A single writer thread owns the SQLite
connection and batches UPSERTs. SQLite in WAL mode gives us one-writer/many-reader
semantics, and funneling writes through one thread removes all contention.
"""
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from . import config, db as dbmod
from .indexer import RowPayload, prepare_row, write_row
from .walker import FileRecord


@dataclass
class RunStats:
    total: int = 0
    ok: int = 0
    errors: int = 0
    skipped: int = 0


_SENTINEL = object()


def _load_existing_mtimes(db_path: Path) -> dict[str, float]:
    conn = dbmod.open_db(db_path)
    try:
        return {path: mtime for path, mtime in conn.execute(
            "SELECT path, mtime FROM files WHERE error IS NULL")}
    finally:
        conn.close()


def _writer_thread(db_path: Path, q: queue.Queue, stats: RunStats,
                   commit_batch: int, progress_cb: Callable[[RowPayload, RunStats], None] | None):
    conn = dbmod.open_db(db_path)
    try:
        conn.execute("BEGIN")
        n_in_txn = 0
        while True:
            item = q.get()
            if item is _SENTINEL:
                break
            try:
                write_row(conn, item)
                if item.error is None:
                    stats.ok += 1
                else:
                    stats.errors += 1
            except Exception as e:
                stats.errors += 1
                # If we can't even record the row, we still don't want to crash the writer.
                # Best-effort: log via progress_cb then keep going.
                item.error = f"writer-error: {type(e).__name__}: {e}"
            if progress_cb is not None:
                try:
                    progress_cb(item, stats)
                except Exception:
                    pass
            n_in_txn += 1
            if n_in_txn >= commit_batch:
                conn.execute("COMMIT")
                conn.execute("BEGIN")
                n_in_txn = 0
        conn.execute("COMMIT")
    finally:
        conn.close()


def run_indexer(
    records: Iterable[FileRecord],
    db_path: Path,
    thumb_root: Path,
    workers: int = 12,
    commit_batch: int = config.COMMIT_BATCH,
    progress_cb: Callable[[RowPayload, RunStats], None] | None = None,
    stop_event: threading.Event | None = None,
) -> RunStats:
    records = list(records)
    stats = RunStats(total=len(records))

    existing = _load_existing_mtimes(db_path)
    to_process: list[FileRecord] = []
    for rec in records:
        prev = existing.get(str(rec.path))
        if prev is not None and abs(prev - rec.mtime) < 1e-6:
            stats.skipped += 1
        else:
            to_process.append(rec)

    if not to_process:
        return stats

    write_q: queue.Queue = queue.Queue(maxsize=max(64, workers * 4))
    writer = threading.Thread(
        target=_writer_thread, daemon=True,
        args=(db_path, write_q, stats, commit_batch, progress_cb),
    )
    writer.start()

    try:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(prepare_row, rec, thumb_root): rec for rec in to_process}
            for fut in as_completed(futures):
                if stop_event is not None and stop_event.is_set():
                    for pending in futures:
                        pending.cancel()
                    break
                try:
                    payload = fut.result()
                except Exception as e:
                    rec = futures[fut]
                    payload = RowPayload(
                        path=str(rec.path), year=rec.year, event_folder=rec.event_folder,
                        filename=rec.filename, ext=rec.ext, kind=rec.kind,
                        bytes=rec.size, mtime=rec.mtime,
                        error=f"{type(e).__name__}: {e}",
                    )
                write_q.put(payload)
    finally:
        write_q.put(_SENTINEL)
        writer.join()

    return stats


def sleep_short(seconds: float, stop_event: threading.Event | None) -> bool:
    """Sleep in 0.2s increments so stop_event can interrupt. Return True if stopped."""
    end = time.time() + seconds
    while time.time() < end:
        if stop_event is not None and stop_event.is_set():
            return True
        time.sleep(min(0.2, end - time.time()))
    return False

"""Progress logger for the threaded indexer runner.

Sits behind runner.run_indexer's `progress_cb` hook and handles:
- Periodic status line to stdout (every `print_every` rows)
- Structured JSONL entry to logs/indexer.log (every row)

Not thread-safe against concurrent callers — but the runner funnels all
progress callbacks through the writer thread, so there is exactly one caller.
"""
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from .indexer import RowPayload
from .runner import RunStats


@dataclass
class ProgressLogger:
    total: int
    log_path: Path | None = None
    print_every: int = 25
    _t0: float = field(default_factory=time.time)
    _processed: int = 0
    _log_fh: TextIO | None = None

    def __post_init__(self) -> None:
        if self.log_path is not None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_fh = self.log_path.open("a", buffering=1)

    def on_row(self, row: RowPayload, stats: RunStats) -> None:
        self._processed += 1
        if self._log_fh is not None:
            entry = {
                "ts": time.time(),
                "path": row.path,
                "kind": row.kind,
                "ok": row.error is None,
                "error": row.error,
            }
            self._log_fh.write(json.dumps(entry) + "\n")
        if self._processed % self.print_every == 0 or self._processed == self.total:
            self._print_line(stats)

    def _print_line(self, stats: RunStats) -> None:
        elapsed = time.time() - self._t0
        rate = self._processed / elapsed if elapsed > 0 else 0.0
        remaining = stats.total - (stats.ok + stats.errors + stats.skipped)
        eta_s = remaining / rate if rate > 0 else float("inf")
        eta = _fmt_duration(eta_s) if eta_s != float("inf") else "?"
        print(
            f"[index] {stats.ok + stats.errors + stats.skipped}/{stats.total} "
            f"(ok={stats.ok} skip={stats.skipped} err={stats.errors}) "
            f"{rate:.1f}/s  ETA {eta}",
            flush=True,
        )

    def finish(self, stats: RunStats) -> None:
        elapsed = time.time() - self._t0
        rate = self._processed / elapsed if elapsed > 0 else 0.0
        print(
            f"[index] done in {_fmt_duration(elapsed)}  "
            f"{rate:.1f}/s  "
            f"ok={stats.ok} skip={stats.skipped} err={stats.errors}",
            flush=True,
        )
        if self._log_fh is not None:
            self._log_fh.close()
            self._log_fh = None


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m{int(seconds % 60):02d}s"
    return f"{int(seconds // 3600)}h{int((seconds % 3600) // 60):02d}m"

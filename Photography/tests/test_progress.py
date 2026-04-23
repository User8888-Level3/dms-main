import json
from pathlib import Path
from photo_index.indexer import RowPayload
from photo_index.runner import RunStats
from photo_index.progress import ProgressLogger


def _row(path: str, err: str | None = None) -> RowPayload:
    return RowPayload(
        path=path, year=2024, event_folder="ev", filename=path,
        ext="jpg", kind="image", bytes=100, mtime=0.0, error=err,
    )


def test_logger_writes_jsonl_per_row(tmp_path: Path):
    log = tmp_path / "indexer.log"
    pl = ProgressLogger(total=3, log_path=log, print_every=10)
    stats = RunStats(total=3)
    for i in range(3):
        stats.ok += 1
        pl.on_row(_row(f"f{i}.jpg"), stats)
    pl.finish(stats)

    lines = log.read_text().strip().splitlines()
    assert len(lines) == 3
    for line in lines:
        entry = json.loads(line)
        assert entry["kind"] == "image"
        assert entry["ok"] is True


def test_logger_captures_errors(tmp_path: Path):
    log = tmp_path / "indexer.log"
    pl = ProgressLogger(total=2, log_path=log, print_every=5)
    stats = RunStats(total=2)
    stats.ok += 1
    pl.on_row(_row("ok.jpg"), stats)
    stats.errors += 1
    pl.on_row(_row("bad.jpg", err="OSError: boom"), stats)
    pl.finish(stats)

    lines = [json.loads(l) for l in log.read_text().strip().splitlines()]
    assert lines[0]["ok"] is True and lines[0]["error"] is None
    assert lines[1]["ok"] is False and lines[1]["error"] == "OSError: boom"


def test_logger_without_log_path(tmp_path: Path, capsys):
    pl = ProgressLogger(total=2, print_every=1)
    stats = RunStats(total=2)
    stats.ok += 1
    pl.on_row(_row("a.jpg"), stats)
    stats.ok += 1
    pl.on_row(_row("b.jpg"), stats)
    pl.finish(stats)
    out = capsys.readouterr().out
    # Printed line per row (print_every=1) + finish line = 3 lines
    assert out.count("[index]") >= 3

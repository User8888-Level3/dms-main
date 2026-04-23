import subprocess
import time
import pytest
from photo_index.retry import smb_retry


def test_retry_returns_value_on_first_try():
    @smb_retry(attempts=3, delay=0.01)
    def ok():
        return "fine"
    assert ok() == "fine"


def test_retry_succeeds_after_transient_failures(monkeypatch):
    calls = {"n": 0}

    @smb_retry(attempts=3, delay=0.01)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("smb blip")
        return "recovered"

    assert flaky() == "recovered"
    assert calls["n"] == 3


def test_retry_reraises_after_exhausting_attempts():
    attempts = {"n": 0}

    @smb_retry(attempts=2, delay=0.01)
    def always_fails():
        attempts["n"] += 1
        raise OSError("permanent")

    with pytest.raises(OSError, match="permanent"):
        always_fails()
    assert attempts["n"] == 2


def test_retry_catches_subprocess_timeout():
    calls = {"n": 0}

    @smb_retry(attempts=2, delay=0.01)
    def timeout_then_ok():
        calls["n"] += 1
        if calls["n"] == 1:
            raise subprocess.TimeoutExpired(cmd="x", timeout=1)
        return "ok"

    assert timeout_then_ok() == "ok"


def test_retry_does_not_catch_other_exceptions():
    @smb_retry(attempts=3, delay=0.01)
    def boom():
        raise ValueError("nope")
    with pytest.raises(ValueError):
        boom()

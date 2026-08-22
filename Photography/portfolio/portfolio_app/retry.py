"""Retry helpers for flaky SMB/subprocess operations.

Defaults pulled from `config.SMB_RETRY` / `config.SMB_RETRY_DELAY`. The intent
is to absorb transient SMB hiccups (`OSError`, `PermissionError`,
`subprocess.TimeoutExpired`) without masking permanent failures.
"""
import functools
import subprocess
import time
from typing import Callable, TypeVar

from . import config

T = TypeVar("T")

_RETRYABLE: tuple[type[BaseException], ...] = (
    OSError,
    subprocess.TimeoutExpired,
)


def smb_retry(attempts: int | None = None, delay: float | None = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    eff_attempts = attempts if attempts is not None else config.SMB_RETRY
    eff_delay = delay if delay is not None else config.SMB_RETRY_DELAY

    def deco(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            last: BaseException | None = None
            for i in range(eff_attempts):
                try:
                    return fn(*args, **kwargs)
                except _RETRYABLE as e:
                    last = e
                    if i < eff_attempts - 1:
                        time.sleep(eff_delay * (2 ** i))
            assert last is not None
            raise last
        return inner
    return deco

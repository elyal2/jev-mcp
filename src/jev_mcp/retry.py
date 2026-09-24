"""Reusable retry decorator with exponential backoff and jitter.

Transient errors (network hiccups, timeouts, throttling, 5xx) are retried;
permanent errors (validation, auth, 4xx other than 429) must fail immediately.
Callers signal which bucket an error falls into by raising `TransientError`
(or a subclass of it) — anything else propagates on the first attempt.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TransientError(Exception):
    """Marker for errors that are safe and worth retrying."""


def retry_on_exception(
    *,
    retries: int = 5,
    delay: float = 2.0,
    cap: float = 32.0,
    timeout: float | None = None,
    exceptions: tuple[type[BaseException], ...] = (TransientError,),
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Exponential backoff (base `delay`, capped at `cap`) with jitter.

    `timeout` wraps each individual attempt in `asyncio.wait_for` as a
    last-resort safety net; a per-attempt timeout is treated as transient.
    Only exceptions in `exceptions` are retried — everything else fails fast.
    """

    async def _backoff_and_log(attempt: int, exc: BaseException) -> None:
        backoff = min(cap, delay * (2 ** (attempt - 1)))
        backoff += random.uniform(0, backoff * 0.1)
        logger.warning(
            "retry.attempt",
            extra={
                "attempt": attempt,
                "max_retries": retries,
                "backoff_seconds": round(backoff, 2),
                "error": str(exc),
            },
        )
        await asyncio.sleep(backoff)

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> T:
            attempt = 0
            while True:
                try:
                    if timeout is not None:
                        return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
                    return await func(*args, **kwargs)
                except TimeoutError as exc:
                    attempt += 1
                    if attempt > retries:
                        raise TransientError(f"timed out after {timeout}s") from exc
                    await _backoff_and_log(attempt, exc)
                except exceptions as exc:
                    attempt += 1
                    if attempt > retries:
                        logger.error(
                            "retry.exhausted",
                            extra={"attempts": attempt, "error": str(exc)},
                        )
                        raise
                    await _backoff_and_log(attempt, exc)

        return wrapper

    return decorator

from __future__ import annotations

import pytest

from jev_mcp.retry import TransientError, retry_on_exception

pytestmark = pytest.mark.unit


async def test_succeeds_on_first_try() -> None:
    calls = 0

    @retry_on_exception(retries=3, delay=0.001, cap=0.002)
    async def fn() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    assert await fn() == "ok"
    assert calls == 1


async def test_retries_transient_then_succeeds() -> None:
    calls = 0

    @retry_on_exception(retries=3, delay=0.001, cap=0.002)
    async def fn() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TransientError("flaky")
        return "ok"

    assert await fn() == "ok"
    assert calls == 3


async def test_exhausts_retries_and_raises() -> None:
    calls = 0

    @retry_on_exception(retries=2, delay=0.001, cap=0.002)
    async def fn() -> str:
        nonlocal calls
        calls += 1
        raise TransientError("always flaky")

    with pytest.raises(TransientError):
        await fn()
    assert calls == 3  # initial attempt + 2 retries


async def test_permanent_error_fails_immediately() -> None:
    calls = 0

    @retry_on_exception(retries=5, delay=0.001, cap=0.002, exceptions=(TransientError,))
    async def fn() -> str:
        nonlocal calls
        calls += 1
        raise ValueError("permanent")

    with pytest.raises(ValueError):
        await fn()
    assert calls == 1


async def test_per_attempt_timeout_is_transient_and_retried() -> None:
    import asyncio

    calls = 0

    @retry_on_exception(retries=2, delay=0.001, cap=0.002, timeout=0.01)
    async def fn() -> str:
        nonlocal calls
        calls += 1
        if calls < 2:
            await asyncio.sleep(1)
        return "ok"

    assert await fn() == "ok"
    assert calls == 2

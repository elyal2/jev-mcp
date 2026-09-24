from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from jev_mcp.client import DecisionAPIError, JevClient
from jev_mcp.config import Settings

pytestmark = pytest.mark.unit


def _response(
    status_code: int, json_body: dict[str, Any] | None = None, text: str = ""
) -> httpx.Response:
    request = httpx.Request("POST", "https://api.typesafe.ai/v1/systemone")
    if json_body is not None:
        return httpx.Response(status_code, json=json_body, request=request)
    return httpx.Response(status_code, text=text, request=request)


async def test_decide_success_returns_body(fast_settings: Settings) -> None:
    client = JevClient(fast_settings)
    ok_body = {"model": "jev-latest", "answers": {"q1": {"type": "noul", "noul": 0.9}}, "usage": {}}

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=_response(200, ok_body))):
        result = await client.decide("some text", {"q1": {"type": "noul", "instructions": "?"}})

    assert result == ok_body


async def test_decide_permanent_400_fails_without_retry(fast_settings: Settings) -> None:
    client = JevClient(fast_settings)
    mock_post = AsyncMock(return_value=_response(400, text="bad request"))

    with patch("httpx.AsyncClient.post", new=mock_post):
        with pytest.raises(DecisionAPIError):
            await client.decide("x", {})

    assert mock_post.call_count == 1


async def test_decide_retries_429_then_succeeds(fast_settings: Settings) -> None:
    client = JevClient(fast_settings)
    ok_body = {"model": "jev-latest", "answers": {}, "usage": {}}
    mock_post = AsyncMock(side_effect=[_response(429, text="slow down"), _response(200, ok_body)])

    with patch("httpx.AsyncClient.post", new=mock_post):
        result = await client.decide("x", {})

    assert result == ok_body
    assert mock_post.call_count == 2


async def test_decide_exhausts_retries_on_persistent_503(fast_settings: Settings) -> None:
    client = JevClient(fast_settings)
    mock_post = AsyncMock(return_value=_response(503, text="down"))

    with patch("httpx.AsyncClient.post", new=mock_post):
        with pytest.raises(DecisionAPIError):
            await client.decide("x", {})

    # fast_settings caps retries at 2 => 1 initial attempt + 2 retries
    assert mock_post.call_count == 3


async def test_decide_network_error_is_transient(fast_settings: Settings) -> None:
    client = JevClient(fast_settings)
    mock_post = AsyncMock(side_effect=httpx.ConnectError("refused"))

    with patch("httpx.AsyncClient.post", new=mock_post):
        with pytest.raises(DecisionAPIError):
            await client.decide("x", {})

    assert mock_post.call_count == 3


async def test_decide_missing_answers_key_is_permanent(fast_settings: Settings) -> None:
    client = JevClient(fast_settings)
    mock_post = AsyncMock(return_value=_response(200, {"model": "jev-latest"}))

    with patch("httpx.AsyncClient.post", new=mock_post):
        with pytest.raises(DecisionAPIError):
            await client.decide("x", {})

    assert mock_post.call_count == 1


async def test_decide_requires_key() -> None:
    client = JevClient(Settings(JEV_API_KEY=""))
    with pytest.raises(RuntimeError):
        await client.decide("x", {})

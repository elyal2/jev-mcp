from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from jev_mcp import server
from jev_mcp.client import DecisionAPIError
from jev_mcp.models import BatchItem, ChoiceQuestion, NoulQuestion, ScoreQuestion

QuestionSpec = ChoiceQuestion | ScoreQuestion | NoulQuestion

pytestmark = pytest.mark.unit


async def test_health_masks_key() -> None:
    with patch.object(server.settings, "jev_api_key", "apikey_supersecret"):
        result = await server.health()
    assert result["has_key"] is True
    assert "supersecret" not in result["key_hint"]
    assert result["key_hint"].startswith("apik")


async def test_decide_propagates_api_error_instead_of_swallowing() -> None:
    """A failed decide() must surface as a raised error, not a disguised dict."""
    with patch.object(
        server._client, "decide", new=AsyncMock(side_effect=DecisionAPIError("boom"))
    ):
        with pytest.raises(DecisionAPIError):
            await server.decide(state="x", questions={})


async def test_decide_returns_body_on_success() -> None:
    body = {"model": "jev-latest", "answers": {"q1": {"type": "noul", "noul": 0.5}}, "usage": {}}
    with patch.object(server._client, "decide", new=AsyncMock(return_value=body)):
        result = await server.decide(state="x", questions={})
    assert result == body


async def test_classify_batch_preserves_order_and_isolates_failures() -> None:
    async def fake_decide(
        state: object, questions: object, model: object = None
    ) -> dict[str, object]:
        if state == "fails":
            raise DecisionAPIError("nope")
        return {"answers": {"q1": {"type": "noul", "noul": 0.1}}}

    items = [
        BatchItem(id="a", state="ok-1"),
        BatchItem(id="b", state="fails"),
        BatchItem(id="c", state="ok-2"),
    ]
    q: dict[str, QuestionSpec] = {"q1": NoulQuestion(instructions="?")}

    with patch.object(server._client, "decide", new=AsyncMock(side_effect=fake_decide)):
        result = await server.classify_batch(items=items, questions=q)

    assert [r["id"] for r in result["results"]] == ["a", "c"]
    assert [e["id"] for e in result["errors"]] == ["b"]
    assert result["count"] == 2

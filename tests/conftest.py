from __future__ import annotations

import pytest

from jev_mcp.config import Settings


@pytest.fixture
def fast_settings() -> Settings:
    """Settings with a real key and near-zero retry delays, for fast tests."""
    return Settings(
        JEV_API_KEY="apikey_test",
        JEV_RETRY_MAX_ATTEMPTS=2,
        JEV_RETRY_BASE_DELAY=0.001,
        JEV_RETRY_CAP_DELAY=0.002,
        JEV_TIMEOUT=1.0,
    )

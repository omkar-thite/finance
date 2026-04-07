"""
Core Pytest Configuration & Fixtures
Provides async support, mock database sessions, and automatic dependency cleanup.
"""

import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock
from main import app
import utils.image_utils as image_utils


@pytest.fixture(scope="session")
def event_loop_policy():
    import asyncio

    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """
    Automatically runs before and after EVERY test.
    Ensures that any dependency overrides set by Copilot/AI in an individual test
    are wiped clean, preventing state bleed into subsequent tests.
    """
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def isolate_profile_pics_dir(tmp_path, monkeypatch):
    """Redirect profile picture writes during tests to a temp directory."""
    test_profile_pics_dir = tmp_path / "profile_pics"
    monkeypatch.setattr(image_utils, "PROFILE_PICS_DIR", test_profile_pics_dir)
    return test_profile_pics_dir


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """
    Provides a fresh AsyncMock session for each test.
    Use this for direct service/CRUD testing, or inject it via overrides for route tests.
    """
    return AsyncMock()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """
    Provides an asynchronous test client for hitting FastAPI routes.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

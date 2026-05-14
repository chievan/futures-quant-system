"""Tests for API endpoints - factor-mine doesn't need DB, others mock it."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app


def _make_mock_session(scalar_one_or_none_return=None, scalars_all_return=None):
    """Create a mock async session with configurable query results.

    After await session.execute(), Result methods (.scalars(), .all(),
    .scalar_one_or_none()) are SYNCHRONOUS — use regular Mock, not AsyncMock.
    """
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    # ScalarsResult mock (SYNC) with .all() and .first()
    mock_scalars = MagicMock()
    if scalars_all_return is not None:
        mock_scalars.all.return_value = scalars_all_return
        mock_scalars.first.return_value = (
            scalars_all_return[0] if scalars_all_return else None
        )

    # Result mock (SYNC) with .scalars() and .scalar_one_or_none()
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    if scalar_one_or_none_return is not None:
        mock_result.scalar_one_or_none.return_value = scalar_one_or_none_return
    else:
        mock_result.scalar_one_or_none.return_value = None

    # execute is a coroutine that returns the mock_result
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.scalar = AsyncMock(return_value=0)

    return mock_session


@pytest.mark.asyncio
async def test_factor_mine_basic():
    """Factor-mine endpoint with a valid expression."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/research/factor-mine", json={
            "expression": "close - low",
            "close": [100.0, 102.0, 101.0, 103.0],
            "high": [101.0, 103.0, 102.0, 104.0],
            "low": [99.0, 101.0, 100.0, 102.0],
            "volume": [1000, 1100, 900, 1200],
            "forward_periods": 2,
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "factor_values" in data
    assert "ic_analysis" in data
    assert data["expression"] == "close - low"


@pytest.mark.asyncio
async def test_factor_mine_no_high_low():
    """Factor-mine uses close as default for high/low."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/research/factor-mine", json={
            "expression": "close",
            "close": [100.0, 102.0, 101.0],
            "forward_periods": 1,
        })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_factor_mine_invalid_expression():
    """Invalid expression returns 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/research/factor-mine", json={
            "expression": "invalid_func(close)",
            "close": [100.0] * 20,
            "forward_periods": 5,
        })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_health_endpoint():
    """Health check endpoint returns 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_strategies_empty():
    """GET /api/strategies/ with mocked DB."""
    mock_session = _make_mock_session(scalars_all_return=[])

    with patch('app.api.strategies.async_session_factory', return_value=mock_session):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/strategies/")

    assert resp.status_code == 200
    data = resp.json()
    assert data["strategies"] == []


@pytest.mark.asyncio
async def test_get_strategy_not_found():
    """GET /api/strategies/999 returns 404."""
    mock_session = _make_mock_session(scalar_one_or_none_return=None)

    with patch('app.api.strategies.async_session_factory', return_value=mock_session):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/strategies/999")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_strategy_duplicate():
    """POST /api/strategies/ with duplicate name returns 400."""
    from app.models.strategy import StrategyConfig

    existing = MagicMock(spec=StrategyConfig)
    existing.name = "test"
    existing.config_json = "{}"

    mock_session = _make_mock_session(scalar_one_or_none_return=existing)

    with patch('app.api.strategies.async_session_factory', return_value=mock_session):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/strategies/", json={
                "name": "test",
                "config_json": '{"fast": 10}',
            })

    assert resp.status_code == 400
    assert "already exists" in resp.text


@pytest.mark.asyncio
async def test_delete_strategy_not_found():
    """DELETE /api/strategies/999 returns 404."""
    mock_session = _make_mock_session(scalar_one_or_none_return=None)

    with patch('app.api.strategies.async_session_factory', return_value=mock_session):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/strategies/999")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_research_tasks_empty():
    """GET /api/research/tasks with mocked DB."""
    mock_session = _make_mock_session(scalars_all_return=[])

    with patch('app.api.research.async_session_factory', return_value=mock_session):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/research/tasks")

    assert resp.status_code == 200
    data = resp.json()
    assert data["tasks"] == []


@pytest.mark.asyncio
async def test_get_research_task_not_found():
    """GET /api/research/tasks/nonexistent returns 404."""
    mock_session = _make_mock_session(scalar_one_or_none_return=None)

    with patch('app.api.research.async_session_factory', return_value=mock_session):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/research/tasks/nonexistent-id")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_research_backtest_validation():
    """POST /api/research/backtest with missing fields returns 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/research/backtest", json={
            "strategy_id": 1,
            # missing params, symbol, start_date, end_date
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_research_search_validation():
    """POST /api/research/search with missing fields returns 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/research/search", json={})
    assert resp.status_code == 422

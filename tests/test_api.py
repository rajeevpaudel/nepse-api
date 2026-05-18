import pytest
from httpx import AsyncClient, ASGITransport
from db.database import get_session
from auth import require_api_key


@pytest.mark.asyncio
async def test_health_check():
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_search_securities(async_session):
    from main import app
    from db.models import Security
    from datetime import datetime

    async def _override_session():
        yield async_session

    async def _override_auth():
        pass

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[require_api_key] = _override_auth

    async_session.add(Security(
        nepse_id=300, symbol="NABIL", name="Nabil Bank Ltd",
        is_active=True, updated_at=datetime.utcnow(),
    ))
    await async_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/securities/search?q=NABIL")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["symbol"] == "NABIL"

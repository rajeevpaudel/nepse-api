import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_sync_securities_upserts(async_session):
    mock_data = [
        {"id": 100, "symbol": "ABC", "securityName": "ABC Ltd", "activeStatus": "A"},
        {"id": 101, "symbol": "DEF", "securityName": "DEF Ltd", "activeStatus": "D"},
    ]
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_data
    mock_response.raise_for_status = MagicMock()

    with patch("scraper.securities.httpx.AsyncClient") as MockClient, \
         patch("scraper.securities.get_ssl_bundle", new=AsyncMock(return_value="/fake/bundle.pem")):
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_response)
        from scraper.securities import sync_securities
        count = await sync_securities(tokens=("fake_access", "fake_refresh"), session=async_session)

    assert count == 2

    from sqlalchemy import select
    from db.models import Security
    result = await async_session.execute(select(Security))
    securities = result.scalars().all()
    assert len(securities) == 2

    abc = next(s for s in securities if s.symbol == "ABC")
    assert abc.is_active is True
    assert abc.nepse_id == 100

    def_sec = next(s for s in securities if s.symbol == "DEF")
    assert def_sec.is_active is False


@pytest.mark.asyncio
async def test_sync_securities_updates_existing(async_session):
    """Running sync twice updates existing records (upsert behaviour)."""
    mock_data = [
        {"id": 100, "symbol": "ABC", "securityName": "ABC Ltd v1", "activeStatus": "A"},
    ]
    mock_data_v2 = [
        {"id": 100, "symbol": "ABC", "securityName": "ABC Ltd v2", "activeStatus": "D"},
    ]
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    with patch("scraper.securities.httpx.AsyncClient") as MockClient, \
         patch("scraper.securities.get_ssl_bundle", new=AsyncMock(return_value="/fake/bundle.pem")):
        instance = MockClient.return_value.__aenter__.return_value
        mock_resp.json.return_value = mock_data
        instance.get = AsyncMock(return_value=mock_resp)
        from scraper.securities import sync_securities
        await sync_securities(tokens=("t", "t"), session=async_session)

        mock_resp.json.return_value = mock_data_v2
        instance.get = AsyncMock(return_value=mock_resp)
        await sync_securities(tokens=("t", "t"), session=async_session)

    from sqlalchemy import select
    from db.models import Security
    result = await async_session.execute(select(Security))
    securities = result.scalars().all()
    assert len(securities) == 1  # No duplicates
    assert securities[0].name == "ABC Ltd v2"
    assert securities[0].is_active is False

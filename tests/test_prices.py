import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_fetch_price_returns_ltp():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'{"securityDailyTradeDto": {"lastTradedPrice": 152.5}}'
    mock_response.json.return_value = {"securityDailyTradeDto": {"lastTradedPrice": 152.5}}

    with patch("scraper.prices.httpx.AsyncClient") as MockClient, \
         patch("scraper.prices.get_ssl_bundle", new=AsyncMock(return_value="/fake/bundle.pem")), \
         patch("scraper.prices.get_payload_id", new=AsyncMock(return_value=42)):
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_response)
        from scraper.prices import fetch_price
        price = await fetch_price(nepse_id=9192, tokens=("fake_access", "fake_refresh"))

    assert price == 152.5


@pytest.mark.asyncio
async def test_fetch_price_returns_none_when_dto_missing():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'{"securityDailyTradeDto": null}'
    mock_response.json.return_value = {"securityDailyTradeDto": None}

    with patch("scraper.prices.httpx.AsyncClient") as MockClient, \
         patch("scraper.prices.get_ssl_bundle", new=AsyncMock(return_value="/fake/bundle.pem")), \
         patch("scraper.prices.get_payload_id", new=AsyncMock(return_value=42)):
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_response)
        from scraper.prices import fetch_price
        price = await fetch_price(nepse_id=9192, tokens=("fake_access", "fake_refresh"))

    assert price is None


@pytest.mark.asyncio
async def test_fetch_price_returns_none_on_401():
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.content = b""

    with patch("scraper.prices.httpx.AsyncClient") as MockClient, \
         patch("scraper.prices.get_ssl_bundle", new=AsyncMock(return_value="/fake/bundle.pem")), \
         patch("scraper.prices.get_payload_id", new=AsyncMock(return_value=42)):
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_response)
        from scraper.prices import fetch_price
        price = await fetch_price(nepse_id=9192, tokens=("fake_access", "fake_refresh"))

    assert price is None

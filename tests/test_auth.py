import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_calc_new_tokens_returns_tuple():
    mock_prove = {
        "salt1": 3, "salt2": 1, "salt3": 2, "salt4": 4, "salt5": 5,
        "accessToken": "a" * 60,
        "refreshToken": "b" * 60,
    }
    with patch("scraper.auth.get_prove_token", new=AsyncMock(return_value=mock_prove)), \
         patch("scraper.auth.calculate_tokens", return_value=("real_access", "real_refresh")), \
         patch("scraper.auth.download_wasm_file", new=AsyncMock(return_value=".cache/css.wasm")):
        from scraper.auth import calc_new_tokens
        access, refresh = await calc_new_tokens()
    assert access == "real_access"
    assert refresh == "real_refresh"

# backend/tests/test_ssl_bundle.py
import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_get_ssl_bundle_returns_path(tmp_path):
    from scraper.ssl_bundle import get_ssl_bundle
    result = await get_ssl_bundle(cache_dir=str(tmp_path / ".cache"))
    assert Path(result).exists()
    assert result.endswith(".pem")

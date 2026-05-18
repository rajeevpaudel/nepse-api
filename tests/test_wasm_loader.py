import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_download_wasm_creates_file(tmp_path):
    from scraper.wasm_loader import download_wasm_file
    path = await download_wasm_file(cache_dir=str(tmp_path / ".cache"))
    assert Path(path).exists()
    assert Path(path).stat().st_size > 0


def test_calculate_tokens_returns_strings(tmp_path):
    from scraper.wasm_loader import calculate_tokens
    # This test requires a real WASM file
    wasm_path = Path(".cache/css.wasm")
    if not wasm_path.exists():
        pytest.skip("WASM file not in .cache — run download_wasm_file() first")
    access, refresh = calculate_tokens(str(wasm_path), "a" * 50, "b" * 50, [1, 2, 3, 4, 5])
    assert isinstance(access, str)
    assert isinstance(refresh, str)
    # Tokens are shorter than input (WASM removes chars at computed indices)
    assert len(access) < 50
    assert len(refresh) < 50

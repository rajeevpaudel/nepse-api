import shutil
from pathlib import Path

import httpx
import wasmtime

from scraper.ssl_bundle import get_ssl_bundle
from config import CACHE_DIR

WASM_URL = "https://nepalstock.com.np/assets/prod/css.wasm"
WASM_HEADERS = {
    "Accept": "application/wasm,application/octet-stream,*/*",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Cache-Control": "no-cache",
}


async def download_wasm_file(cache_dir: str | None = None) -> str:
    base = Path(cache_dir or CACHE_DIR)
    base.mkdir(parents=True, exist_ok=True)
    wasm_path = base / "css.wasm"
    if not wasm_path.exists():
        ssl_bundle = await get_ssl_bundle(cache_dir=cache_dir)
        async with httpx.AsyncClient(verify=ssl_bundle) as client:
            resp = await client.get(WASM_URL, headers=WASM_HEADERS, timeout=30)
            if resp.status_code in (429, 500, 502, 503, 504):
                resp = await client.get(WASM_URL, headers=WASM_HEADERS, timeout=30)
            resp.raise_for_status()
        wasm_path.write_bytes(resp.content)
    return str(wasm_path)


def calculate_tokens(
    wasm_path: str,
    access_token: str,
    refresh_token: str,
    salts: list[int],
) -> tuple[str, str]:
    engine = wasmtime.Engine()
    linker = wasmtime.Linker(engine)
    linker.define_wasi()
    store = wasmtime.Store(engine)
    module = wasmtime.Module.from_file(engine, wasm_path)
    instance = linker.instantiate(store, module)
    exports = instance.exports(store)

    def call_wasm(fn, *args):
        return exports[fn](store, *args)

    s1, s2, s3, s4, s5 = salts

    a_cdx = call_wasm("cdx", s1, s2, s3, s4, s5)
    a_rdx = call_wasm("rdx", s1, s2, s4, s3, s5)
    a_bdx = call_wasm("bdx", s1, s2, s4, s3, s5)
    a_ndx = call_wasm("ndx", s1, s2, s4, s3, s5)
    a_mdx = call_wasm("mdx", s1, s2, s4, s3, s5)

    new_access = (
        access_token[:a_cdx] + access_token[a_cdx + 1:a_rdx] +
        access_token[a_rdx + 1:a_bdx] + access_token[a_bdx + 1:a_ndx] +
        access_token[a_ndx + 1:a_mdx] + access_token[a_mdx + 1:]
    )

    r_cdx = call_wasm("cdx", s2, s1, s3, s5, s4)
    r_rdx = call_wasm("rdx", s2, s1, s3, s4, s5)
    r_bdx = call_wasm("bdx", s2, s1, s4, s3, s5)
    r_ndx = call_wasm("ndx", s2, s1, s4, s3, s5)
    r_mdx = call_wasm("mdx", s2, s1, s4, s3, s5)

    new_refresh = (
        refresh_token[:r_cdx] + refresh_token[r_cdx + 1:r_rdx] +
        refresh_token[r_rdx + 1:r_bdx] + refresh_token[r_bdx + 1:r_ndx] +
        refresh_token[r_ndx + 1:r_mdx] + refresh_token[r_mdx + 1:]
    )

    return new_access, new_refresh


def clear_cache(cache_dir: str | None = None) -> None:
    base = Path(cache_dir or CACHE_DIR)
    if base.exists():
        shutil.rmtree(base)

from datetime import datetime, timezone
import httpx
from scraper.ssl_bundle import get_ssl_bundle
from scraper.wasm_loader import download_wasm_file, calculate_tokens

PROVE_URL = "https://nepalstock.com.np/api/authenticate/prove"
PROVE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
}


async def get_prove_token() -> dict:
    ssl_bundle = await get_ssl_bundle()
    async with httpx.AsyncClient(verify=ssl_bundle) as client:
        resp = await client.get(PROVE_URL, headers=PROVE_HEADERS, timeout=30)
        resp.raise_for_status()
    return resp.json()


async def calc_new_tokens() -> tuple[str, str]:
    prove = await get_prove_token()
    salts = [prove["salt1"], prove["salt2"], prove["salt3"], prove["salt4"], prove["salt5"]]
    wasm_path = await download_wasm_file()
    access, refresh = calculate_tokens(wasm_path, prove["accessToken"], prove["refreshToken"], salts)
    return access, refresh


async def get_or_refresh_tokens(session, force: bool = False) -> tuple[str, str]:
    """Load tokens from DB; refresh and persist if older than 2 minutes, missing, or forced."""
    from sqlalchemy import select, delete
    from db.models import NepseToken

    if not force:
        result = await session.execute(
            select(NepseToken).order_by(NepseToken.fetched_at.desc()).limit(1)
        )
        token_row = result.scalar_one_or_none()

        if token_row:
            fetched_at = token_row.fetched_at
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - fetched_at).total_seconds()
            if age < 120:
                return token_row.access_token, token_row.refresh_token

    access, refresh = await calc_new_tokens()
    await session.execute(delete(NepseToken))
    session.add(NepseToken(
        access_token=access,
        refresh_token=refresh,
        fetched_at=datetime.now(timezone.utc),
    ))
    await session.commit()
    return access, refresh

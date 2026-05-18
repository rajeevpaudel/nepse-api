import httpx
from scraper.ssl_bundle import get_ssl_bundle
from scraper.payload_calc import get_payload_id

PRICE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Connection": "keep-alive",
    "Origin": "https://nepalstock.com.np",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0",
}

async def fetch_price(nepse_id: int, tokens: tuple[str, str]) -> float | None:
    """
    POST to NEPSE price endpoint. Returns lastTradedPrice or None on 401/403.
    """
    access_token, _ = tokens
    ssl_bundle = await get_ssl_bundle()
    payload_id = await get_payload_id(access_token)
    url = f"https://nepalstock.com.np/api/nots/security/{nepse_id}"
    headers = {
        **PRICE_HEADERS,
        "Authorization": f"Salter {access_token}",
        "Referer": f"https://nepalstock.com.np/company/detail/{nepse_id}",
    }
    async with httpx.AsyncClient(verify=ssl_bundle) as client:
        resp = await client.post(
            url,
            headers=headers,
            json={"id": payload_id},
            timeout=30,
        )
    if resp.status_code in (401, 403):
        return None
    try:
        body = resp.json() if resp.content else {}
    except Exception:
        body = {}
    dto = (body.get("securityDailyTradeDto") or {})
    return dto.get("lastTradedPrice")

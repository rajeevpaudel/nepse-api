from datetime import datetime
import httpx
from scraper.ssl_bundle import get_ssl_bundle

MARKET_OPEN_URL = "https://nepalstock.com.np/api/nots/nepse-data/market-open"
_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
}

_DATA = [
    147, 117, 239, 143, 157, 312, 161, 612, 512, 804,
    411, 527, 170, 511, 421, 667, 764, 621, 301, 106,
    133, 793, 411, 511, 312, 423, 344, 346, 653, 758,
    342, 222, 236, 811, 711, 611, 122, 447, 128, 199,
    183, 135, 489, 703, 800, 745, 152, 863, 134, 211,
    142, 564, 375, 793, 212, 153, 138, 153, 648, 611,
    151, 649, 318, 143, 117, 756, 119, 141, 717, 113,
    112, 146, 162, 660, 693, 261, 362, 354, 251, 641,
    157, 178, 631, 192, 734, 445, 192, 883, 187, 122,
    591, 731, 852, 384, 565, 596, 451, 772, 624, 691,
]

_cached_id: int | None = None
_cached_day: int | None = None


async def get_payload_id(access_token: str) -> int:
    global _cached_id, _cached_day
    today = datetime.now().day
    if _cached_id is not None and _cached_day == today:
        return _cached_id

    ssl_bundle = await get_ssl_bundle()
    headers = {**_HEADERS, "Authorization": f"Salter {access_token}"}
    async with httpx.AsyncClient(verify=ssl_bundle) as client:
        response = await client.get(MARKET_OPEN_URL, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

    provided_id = data.get("id")
    if provided_id is None:
        raise ValueError("market-open response missing 'id'")
    if provided_id >= len(_DATA):
        raise ValueError(f"market-open id={provided_id} out of range for lookup table")

    _cached_id = _DATA[provided_id] + provided_id + 2 * today
    _cached_day = today
    return _cached_id


if __name__ == "__main__":
    import asyncio
    from scraper.auth import calc_new_tokens as get_auth_tokens

    async def _run():
        access, _ = await get_auth_tokens()
        payload_id = await get_payload_id(access)
        print(f"Payload id: {payload_id}")

    asyncio.run(_run())

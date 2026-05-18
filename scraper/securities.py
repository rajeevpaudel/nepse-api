import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import Security
from scraper.ssl_bundle import get_ssl_bundle
from datetime import datetime, timezone

SECURITIES_URL = "https://nepalstock.com.np/api/nots/security?nonDelisted=true"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0",
}


async def sync_securities(tokens: tuple[str, str], session: AsyncSession) -> int:
    access_token, _ = tokens
    ssl_bundle = await get_ssl_bundle()
    headers = {**HEADERS, "Authorization": f"Salter {access_token}"}
    async with httpx.AsyncClient(verify=ssl_bundle) as client:
        resp = await client.get(SECURITIES_URL, headers=headers, timeout=60)
        resp.raise_for_status()
    data = resp.json()

    for item in data:
        result = await session.execute(
            select(Security).where(Security.nepse_id == item["id"])
        )
        existing = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        is_active = (item["activeStatus"] == "A")
        if existing:
            existing.symbol = item["symbol"]
            existing.name = item["securityName"]
            existing.is_active = is_active
            existing.updated_at = now
        else:
            session.add(Security(
                nepse_id=item["id"],
                symbol=item["symbol"],
                name=item["securityName"],
                is_active=is_active,
                updated_at=now,
            ))

    await session.commit()
    return len(data)

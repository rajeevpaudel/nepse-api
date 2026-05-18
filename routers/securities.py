from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from db.database import get_session
from db.models import Security
from scraper.auth import get_or_refresh_tokens
from scraper.prices import fetch_price
from scraper.securities import sync_securities

router = APIRouter(prefix="/securities", tags=["securities"])


@router.get("")
async def list_securities(
    page: int = 1,
    page_size: int = 50,
    session: AsyncSession = Depends(get_session),
):
    offset = (page - 1) * page_size
    result = await session.execute(
        select(Security)
        .where(Security.is_active.is_(True))
        .order_by(Security.symbol)
        .offset(offset)
        .limit(page_size)
    )
    secs = result.scalars().all()
    return [{"nepse_id": s.nepse_id, "symbol": s.symbol, "name": s.name} for s in secs]


@router.post("/sync")
async def trigger_sync_securities(session: AsyncSession = Depends(get_session)):
    tokens = await get_or_refresh_tokens(session)
    count = await sync_securities(tokens, session)
    return {"status": "done", "synced": count}


@router.get("/{symbol}/price")
async def get_latest_price(
    symbol: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Security).where(
            Security.symbol == symbol.upper(),
            Security.is_active.is_(True),
        )
    )
    sec = result.scalar_one_or_none()
    if sec is None:
        raise HTTPException(status_code=404, detail=f"Security '{symbol.upper()}' not found")

    tokens = await get_or_refresh_tokens(session)
    for _ in range(3):
        price = await fetch_price(sec.nepse_id, tokens)
        if price is not None:
            return {"symbol": sec.symbol, "name": sec.name, "last_traded_price": price}

    tokens = await get_or_refresh_tokens(session, force=True)
    price = await fetch_price(sec.nepse_id, tokens)
    if price is None:
        raise HTTPException(status_code=503, detail="Price unavailable — NEPSE returned no data")

    return {"symbol": sec.symbol, "name": sec.name, "last_traded_price": price}

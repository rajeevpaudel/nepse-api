import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from db.database import SessionLocal
from db.models import NepseToken
from scraper.wasm_loader import download_wasm_file, clear_cache
from scraper.auth import calc_new_tokens
from sqlalchemy import delete

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Kathmandu")


async def _market_open_job():
    """Run once at 10:00 NST: clear cache, download WASM, persist fresh tokens."""
    logger.info("Market open: initializing")
    clear_cache()
    await download_wasm_file()
    async with SessionLocal() as session:
        tokens = await calc_new_tokens()
        await session.execute(delete(NepseToken))
        session.add(NepseToken(
            access_token=tokens[0],
            refresh_token=tokens[1],
            fetched_at=datetime.now(timezone.utc),
        ))
        await session.commit()
    logger.info("Market open initialization complete")


async def _market_close_job():
    """Run at 15:01 NST: clear WASM and SSL cache."""
    logger.info("Market close: clearing cache")
    clear_cache()


def setup_scheduler() -> AsyncIOScheduler:
    # Market open: Mon-Fri 10:00 NST
    scheduler.add_job(
        _market_open_job,
        CronTrigger(day_of_week="mon,tue,wed,thu,fri", hour=10, minute=0, timezone="Asia/Kathmandu"),
        id="market_open",
    )
    # Market close: Mon-Fri 15:01 NST
    scheduler.add_job(
        _market_close_job,
        CronTrigger(day_of_week="mon,tue,wed,thu,fri", hour=15, minute=1, timezone="Asia/Kathmandu"),
        id="market_close",
    )
    return scheduler

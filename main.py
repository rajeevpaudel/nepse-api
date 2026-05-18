import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy import func, select
from config import DEBUG_MODE
from auth import require_api_key
from db.init_db import create_tables
from db.database import SessionLocal
from db.models import Security
from scraper.auth import calc_new_tokens
from scraper.securities import sync_securities
from routers import securities as securities_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

async def _seed_securities_if_empty():
    async with SessionLocal() as session:
        count = await session.scalar(select(func.count()).select_from(Security))
        if count == 0:
            logger.info("Securities table is empty — seeding on startup")
            tokens = await calc_new_tokens()
            n = await sync_securities(tokens, session)
            logger.info(f"Seeded {n} securities")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    await _seed_securities_if_empty()
    if DEBUG_MODE:
        logger.warning("DEBUG_MODE is ON — /debug/* endpoints are active")
    yield

app = FastAPI(title="NEPSE Alert", lifespan=lifespan)

_auth = [Depends(require_api_key)]
app.include_router(securities_router.router, dependencies=_auth)

if DEBUG_MODE:
    from routers import debug as debug_router
    app.include_router(debug_router.router, dependencies=_auth)

@app.get("/health")
async def health():
    return {"status": "ok", "debug_mode": DEBUG_MODE}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

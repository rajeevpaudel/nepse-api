from fastapi import APIRouter
from services.scheduler import _market_open_job

router = APIRouter(prefix="/debug", tags=["debug"])


@router.post("/run-market-open")
async def trigger_market_open():
    """Re-run the market-open job: clear cache, download WASM, sync securities, refresh tokens."""
    await _market_open_job()
    return {"status": "done"}

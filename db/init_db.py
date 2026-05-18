from db.database import engine, Base
import db.models  # noqa: F401 — registers all models with Base

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

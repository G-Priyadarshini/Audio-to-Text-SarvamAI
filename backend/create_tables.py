import asyncio
from app.database import engine
from app.models import Base


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created / verified")


if __name__ == "__main__":
    asyncio.run(main())
import asyncio
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("create_tables")

try:
    from app.models.base import Base
    from app.database import engine
except Exception as e:
    logger.error("Failed to import Base or engine: %s", e)
    sys.exit(1)

async def _create_async():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def create_all():
    # engine is an AsyncEngine in this project
    try:
        asyncio.run(_create_async())
    except Exception as e:
        logger.error("Failed to create tables: %s", e)
        raise

if __name__ == "__main__":
    logger.info("Creating DB tables (if missing)...")
    create_all()
    logger.info("Done.")

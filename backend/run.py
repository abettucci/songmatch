import sys
import asyncio
import uvicorn
from app.core.config import get_settings

# asyncpg requires SelectorEventLoop on Windows (ProactorEventLoop causes
# ConnectionDoesNotExistError during the PostgreSQL protocol handshake)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

settings = get_settings()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level="info",
        loop="asyncio",
    )

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from app.core.config import get_settings
from app.db.models import Base

logger = logging.getLogger(__name__)
settings = get_settings()

engine = None
async_session_maker = None


def get_database_url() -> str:
    url = settings.database_url
    # Normalize to postgresql+psycopg (psycopg3) — works reliably on Windows
    for prefix in ("postgresql+asyncpg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix):]
            break
    return url


async def init_db():
    global engine, async_session_maker
    
    if not settings.database_url:
        logger.warning("DATABASE_URL not set, database features will be disabled")
        return
    
    database_url = get_database_url()
    
    engine = create_async_engine(
        database_url,
        echo=settings.debug,
        poolclass=NullPool,
    )
    
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    logger.info("Database connection pool initialized")


async def close_db():
    global engine
    if engine:
        await engine.dispose()
        logger.info("Database connection pool closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if async_session_maker is None:
        raise RuntimeError("Database not initialized")
    
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    if async_session_maker is None:
        raise RuntimeError("Database not initialized")
    
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

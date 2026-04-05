"""Database engine and session management for SpikeEO."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from spikeeo.config import get_settings
from spikeeo.db.models import Base

logger = logging.getLogger(__name__)

_settings = get_settings()
_is_sqlite = _settings.database_url.startswith("sqlite")

_connect_args = {"check_same_thread": False} if _is_sqlite else {}
_pool_kwargs = {"poolclass": StaticPool} if _is_sqlite else {}

engine = create_async_engine(
    _settings.database_url,
    echo=_settings.app_debug,
    connect_args=_connect_args,
    **_pool_kwargs,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

logger.info("Database engine created: %s", _settings.database_url.split("@")[-1])


async def init_db() -> None:
    """Create all database tables if they don't already exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialised")


async def get_db() -> "AsyncGenerator[AsyncSession, None]":  # type: ignore[return]
    """FastAPI dependency that yields an async DB session."""
    from collections.abc import AsyncGenerator
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

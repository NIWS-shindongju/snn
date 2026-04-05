"""Database engine and session management.

Supports SQLite (default, async via aiosqlite) and
PostgreSQL (via asyncpg) determined by DATABASE_URL.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from carbonsnn.config import get_settings
from carbonsnn.db.models import Base

logger = logging.getLogger(__name__)

_settings = get_settings()

# ── Engine creation ───────────────────────────────────────

_is_sqlite = _settings.database_url.startswith("sqlite")

_connect_args: dict = {}
_pool_class = None

if _is_sqlite:
    # SQLite requires check_same_thread=False for multi-threaded use
    _connect_args = {"check_same_thread": False}
    _pool_class = StaticPool

engine = create_async_engine(
    _settings.database_url,
    echo=_settings.app_debug,
    connect_args=_connect_args,
    **({} if not _is_sqlite else {"poolclass": _pool_class}),
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

logger.info("Database engine created: %s", _settings.database_url.split("@")[-1])


# ── Schema bootstrap ──────────────────────────────────────

async def init_db() -> None:
    """Create all tables if they don't already exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialised")


# ── Dependency ────────────────────────────────────────────

async def get_db() -> "AsyncGenerator[AsyncSession, None]":  # type: ignore[return]
    """FastAPI dependency that yields an async DB session.

    Yields:
        AsyncSession that is committed on success and rolled back on error.
    """
    from collections.abc import AsyncGenerator  # noqa: PLC0415

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

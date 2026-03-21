"""
Neon PostgreSQL Client
=======================
Async SQLAlchemy connection pool for Neon PostgreSQL.
Uses asyncpg driver for maximum performance.

Connection strategy:
  - Single pool shared across all FastAPI workers
  - Pool size: 5 connections (sufficient for Railway free tier)
  - SSL required (Neon enforces TLS)
  - Prepared statements disabled (Neon serverless requires this)
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine (module-level singleton)
# ---------------------------------------------------------------------------

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def _build_engine() -> AsyncEngine:
    """
    Build the SQLAlchemy async engine for Neon PostgreSQL.

    Neon requires:
    - asyncpg driver (postgresql+asyncpg://)
    - SSL mode = require
    - prepared_statement_cache_size=0 (Neon serverless limitation)
    """
    db_url = settings.DATABASE_URL

    # Ensure we're using asyncpg driver
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)

    # Strip query params that asyncpg doesn't accept (ssl handled via connect_args)
    if "?" in db_url:
        base, _ = db_url.split("?", 1)
        db_url = base

    return create_async_engine(
        db_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,         # Verify connections before use
        pool_recycle=300,           # Recycle connections every 5 min (Neon idle timeout)
        echo=settings.APP_ENV == "development",  # Log SQL in dev only
        connect_args={
            "ssl": True,
            "prepared_statement_cache_size": 0,  # Required for Neon serverless
            "statement_cache_size": 0,
        },
    )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """Initialise the database connection pool. Called on app startup."""
    global _engine, _session_factory

    _engine = _build_engine()
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Verify connection
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection established successfully")
    except Exception as exc:
        logger.error("Database connection failed: %s", exc)
        raise


async def close_db() -> None:
    """Close all database connections. Called on app shutdown."""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("Database connections closed")


# ---------------------------------------------------------------------------
# Dependency for FastAPI routes
# ---------------------------------------------------------------------------

@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[AsyncConnection, None]:
    """Provide a raw async connection (for bulk operations / migrations)."""
    if _engine is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    async with _engine.begin() as conn:
        yield conn


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency: provides an async database session.

    Usage in routers:
        async def my_route(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

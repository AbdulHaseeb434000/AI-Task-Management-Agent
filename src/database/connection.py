"""Database connection management for PostgreSQL.

Provides both async and sync database sessions.
"""

import sys
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

# Add config to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import get_settings
from src.database.orm import Base

settings = get_settings()

# Async engine for FastAPI
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# Sync engine for migrations and Celery
sync_engine = create_engine(
    settings.database_url_sync,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

# Session factories
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autoflush=False,
    autocommit=False,
)


async def init_db() -> None:
    """Initialize database tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    """Drop all database tables (use with caution)."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def init_db_sync() -> None:
    """Initialize database tables synchronously."""
    Base.metadata.create_all(bind=sync_engine)


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session."""
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Get a sync database session."""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ============================================================================
# SQLite compatibility layer for legacy orchestrator code
# TODO: Remove after unifying dual agent systems
# ============================================================================

import sqlite3
from contextlib import contextmanager

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "tasks.db"


@contextmanager
def get_db(db_path: Path = DEFAULT_DB_PATH):
    """Get a SQLite connection (legacy compatibility).

    This is for backward compatibility with the orchestrator agent.
    New code should use get_async_session() or get_sync_session().
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_sqlite_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Initialize SQLite database tables (legacy compatibility)."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 3,
                created_at TEXT,
                updated_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                plan_id TEXT,
                parent_id TEXT,
                subtask_ids TEXT DEFAULT '[]',
                dependencies TEXT DEFAULT '[]',
                assigned_agent TEXT,
                result TEXT,
                error TEXT,
                metadata TEXT DEFAULT '{}',
                tags TEXT DEFAULT '[]'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                strategy TEXT,
                steps TEXT DEFAULT '[]',
                created_at TEXT,
                total_estimated_minutes INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_logs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                agent_type TEXT,
                action TEXT,
                input TEXT,
                output TEXT,
                error TEXT,
                started_at TEXT,
                completed_at TEXT,
                duration_ms INTEGER
            )
        """)
        conn.commit()

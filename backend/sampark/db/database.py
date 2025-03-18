import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Load environment variables
load_dotenv()

# Database path from environment variable with fallback
DB_PATH = Path(os.getenv("DB_PATH", "./data/sampark.db"))


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


# Create the parent directory if it doesn't exist
def ensure_db_path_exists() -> None:
    """Ensure the database directory exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# Create the SQLAlchemy engine and sessionmaker
# Using SQLite with aiosqlite for async support
engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions to ensure proper resource cleanup.

    Usage:
        async with get_db_session() as session:
            # Use session for database operations
            # Commits or rollbacks are handled automatically

    Yields:
        AsyncSession: The database session.
    """
    session = async_session_maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get a database session."""
    async with async_session_maker() as session:
        yield session


async def init_db() -> None:
    """Initialize the database, creating tables if they don't exist."""
    ensure_db_path_exists()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

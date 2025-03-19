"""
Global pytest fixtures for all tests.
"""

import pytest
import pytest_asyncio
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import Dict, Any, cast

from sampark.db.database import Base

# Use in-memory SQLite database for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")  # type: ignore
async def test_engine():  # type: ignore
    """Create a test database engine using in-memory SQLite."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Close the engine
    await engine.dispose()


@pytest_asyncio.fixture  # type: ignore
async def db_session(test_engine):  # type: ignore
    """Create a test database session for dependency injection in tests."""
    # Create a sessionmaker that produces AsyncSession objects
    # Cast the engine to Engine for type checking
    async_session_factory = sessionmaker(bind=cast(Engine, test_engine), expire_on_commit=False, class_=AsyncSession)

    # Create a new session for each test
    session = async_session_factory()

    try:
        # Use the session in the test
        yield session
        # Roll back at the end to isolate tests
        await session.rollback()  # type: ignore
    finally:
        await session.close()  # type: ignore


@pytest.fixture
def email_client_config() -> Dict[str, Any]:
    """Return the email client configuration for tests."""
    return {
        "imap_server": "imap.example.com",
        "imap_port": 993,
        "smtp_server": "smtp.example.com",
        "smtp_port": 587,
        "username": "test@example.com",
        "password": "test_password",
        "mailbox": "INBOX",
    }

"""Pytest fixtures and test configuration.

Uses SQLite in-memory for isolation — no PostgreSQL needed for testing.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User

# ── Async SQLite engine for tests ────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

test_session_factory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Override get_db dependency ────────────────────────────────

async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create tables before each test and drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test DB session."""
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession) -> Tenant:
    """Create a test tenant."""
    tenant = Tenant(id=uuid.uuid4(), name="Test Corp")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    """Create an admin user in the test tenant."""
    user = User(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        email="admin@test.com",
        password_hash=hash_password("AdminPass123"),
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def viewer_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    """Create a viewer user in the test tenant."""
    user = User(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        email="viewer@test.com",
        password_hash=hash_password("ViewerPass123"),
        role="viewer",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_tenant_user(db_session: AsyncSession) -> User:
    """Create a user in a DIFFERENT tenant for cross-tenant tests."""
    other_tenant = Tenant(id=uuid.uuid4(), name="Other Corp")
    db_session.add(other_tenant)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        email="other@other.com",
        password_hash=hash_password("OtherPass123"),
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def make_token(user: User) -> str:
    """Generate an access token for a user."""
    return create_access_token({
        "sub": str(user.id),
        "tenant_id": str(user.tenant_id),
        "role": user.role,
    })


@pytest_asyncio.fixture
async def admin_token(admin_user: User) -> str:
    return make_token(admin_user)


@pytest_asyncio.fixture
async def viewer_token(viewer_user: User) -> str:
    return make_token(viewer_user)


@pytest_asyncio.fixture
async def other_tenant_token(other_tenant_user: User) -> str:
    return make_token(other_tenant_user)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

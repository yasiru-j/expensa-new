"""
Tests run against a real Postgres database (`<owner db>_test`) because RLS
cannot be exercised against SQLite/mocks — the whole point of the security
suite is to prove the database itself enforces isolation.

This file rewrites DATABASE_URL_OWNER / DATABASE_URL_APP to point at a
throwaway "_test" database *before* anything under app/ is imported, so every
module-level engine created downstream targets the test database.
"""

import os
from pathlib import Path

from dotenv import dotenv_values

ROOT_DIR = Path(__file__).resolve().parents[2]
_dotenv_values = dotenv_values(ROOT_DIR / ".env")


def _get(key: str, default: str) -> str:
    return os.environ.get(key) or _dotenv_values.get(key) or default


def _with_test_db(url: str) -> str:
    base, _, dbname = url.rpartition("/")
    return f"{base}/{dbname}_test"


os.environ["DATABASE_URL_OWNER"] = _with_test_db(
    _get(
        "DATABASE_URL_OWNER",
        "postgresql+asyncpg://expensa_owner:changeme-owner-password@localhost:5432/expensa",
    )
)
os.environ["DATABASE_URL_APP"] = _with_test_db(
    _get(
        "DATABASE_URL_APP",
        "postgresql+asyncpg://expensa_app:changeme-app-password@localhost:5432/expensa",
    )
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production-use")
os.environ.setdefault(
    "POSTGRES_APP_PASSWORD", _get("POSTGRES_APP_PASSWORD", "changeme-app-password")
)
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

import asyncio  # noqa: E402
import uuid  # noqa: E402
from collections.abc import AsyncGenerator, AsyncIterator  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

import asyncpg  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.extraction.client import get_openai_client  # noqa: E402
from app.main import app  # noqa: E402
from app.storage.s3 import ensure_bucket_exists  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
settings = get_settings()


def _asyncpg_dsn(sqlalchemy_url: str) -> str:
    return sqlalchemy_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_database() -> None:
    """Drop/recreate the test database and run all migrations, once per test session."""
    owner_dsn = _asyncpg_dsn(settings.database_url_owner)
    base_dsn, _, test_db_name = owner_dsn.rpartition("/")
    admin_dsn = f"{base_dsn}/postgres"

    async def _recreate_db() -> None:
        conn = await asyncpg.connect(admin_dsn)
        try:
            await conn.execute(f'DROP DATABASE IF EXISTS "{test_db_name}" WITH (FORCE)')
            await conn.execute(f'CREATE DATABASE "{test_db_name}"')
        finally:
            await conn.close()

    asyncio.run(_recreate_db())

    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(alembic_cfg, "head")


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _prepare_object_storage() -> None:
    # httpx's ASGITransport (used by the `client` fixture) never fires
    # Starlette lifespan events, so the app's own startup hook that creates
    # the MinIO bucket never runs under test — do it explicitly here instead.
    await ensure_bucket_exists()


@pytest_asyncio.fixture
async def owner_session() -> AsyncGenerator[AsyncSession, None]:
    """Direct owner-role access, for seeding/asserting outside the app's own request path.

    Deliberately separate from app.db.session, which only ever exposes the
    restricted app-role engine the real API uses.
    """
    owner_engine = create_async_engine(settings.database_url_owner, pool_pre_ping=True)
    owner_sessionmaker = async_sessionmaker(bind=owner_engine, expire_on_commit=False)
    async with owner_sessionmaker() as session:
        yield session
    await owner_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(owner_session: AsyncSession) -> None:
    await owner_session.execute(
        text("TRUNCATE TABLE line_items, expenses, usage, users RESTART IDENTITY CASCADE")
    )
    await owner_session.commit()


@pytest.fixture
def app_session_as():
    """Returns a callable: app_session_as(user_id) -> async context manager yielding an
    AsyncSession connected as the restricted expensa_app role, with app.user_id set for
    the transaction (mirroring exactly what get_current_user does per-request).

    Pass user_id=None to open a transaction with no session variable set at all.
    """

    def _factory(user_id: uuid.UUID | None):
        @asynccontextmanager
        async def _ctx() -> AsyncIterator[AsyncSession]:
            async with AsyncSessionLocal() as session, session.begin():
                if user_id is not None:
                    await session.execute(
                        text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)}
                    )
                yield session

        return _ctx()

    return _factory


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def signup_user(client: AsyncClient):
    """Returns a callable: signup_user(email) -> access_token, after registering
    that user through the real signup endpoint."""

    async def _signup(email: str, password: str = "hunter22222") -> str:
        resp = await client.post("/api/auth/signup", json={"email": email, "password": password})
        assert resp.status_code == 201, resp.text
        return resp.json()["access_token"]

    return _signup


@pytest.fixture
def mock_openai_client():
    """Overrides the OpenAI client dependency for the duration of one test, so
    the real API is never called. Yields the AsyncMock for tests to configure
    (.return_value / .side_effect) and assert on (.call_count, etc.)."""
    from unittest.mock import AsyncMock

    fake_client = AsyncMock()
    app.dependency_overrides[get_openai_client] = lambda: fake_client
    yield fake_client
    del app.dependency_overrides[get_openai_client]

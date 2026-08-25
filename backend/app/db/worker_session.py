"""Owner-role session, for the worker's periodic maintenance sweep ONLY.

Deliberately its own module, separate from app/db/session.py, so nothing in
app/api/* can casually import it — the FastAPI app never connects as the
owner role, only app/worker.py does, and only for
sweep_all_stale_processing_rows (see app/db/maintenance.py for why a
periodic cross-user sweep needs this). This does widen the owner
credential's exposure to a second running process; see the README's
async-processing section.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

_owner_engine = create_async_engine(settings.database_url_owner, pool_pre_ping=True)
OwnerSessionLocal = async_sessionmaker(bind=_owner_engine, expire_on_commit=False)


@asynccontextmanager
async def owner_scoped_session() -> AsyncGenerator[AsyncSession, None]:
    async with OwnerSessionLocal() as session, session.begin():
        yield session

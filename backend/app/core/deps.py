import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenType, decode_token
from app.db.models.user import User
from app.db.session import AsyncSessionLocal

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session, session.begin():
        yield session


@asynccontextmanager
async def user_scoped_session(user_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """A short-lived transaction scoped to one user via set_config, committed
    and its connection released on exit.

    Use this — not the request-long get_db session — around any work that also
    does slow external I/O (OpenAI, S3/MinIO PUTs): open a short txn, do the DB
    part, let it commit and close, THEN do the slow I/O with no DB connection
    checked out, then open another short txn to persist the outcome. Each txn
    re-runs set_config independently since the GUC is transaction-local.
    """
    async with AsyncSessionLocal() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)}
        )
        yield session


def _resolve_authenticated_user_id(
    credentials: HTTPAuthorizationCredentials | None,
) -> uuid.UUID:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    if credentials is None:
        raise unauthorized

    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise unauthorized from exc

    if payload.get("type") != TokenType.ACCESS.value:
        raise unauthorized

    return uuid.UUID(payload["sub"])


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = _resolve_authenticated_user_id(credentials)

    # Scope this request's DB transaction to the caller before any other
    # query runs, so Postgres RLS isolates data even if a query forgets a
    # user_id filter. set_config(..., true) is SET LOCAL semantics (resets at
    # end of transaction) expressed as a function call, since SET LOCAL's
    # own grammar doesn't accept a bind parameter for the value.
    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)})

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    return user


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> uuid.UUID:
    """Authenticates via JWT + a short-lived DB check, WITHOUT holding a
    connection open for the rest of the request. Use this instead of
    get_current_user for any handler that does slow external I/O after
    authenticating (e.g. the upload endpoint), so the DB pool isn't tied up
    idling on that I/O.
    """
    user_id = _resolve_authenticated_user_id(credentials)

    async with user_scoped_session(user_id) as session:
        user = await session.get(User, user_id)

    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    return user_id

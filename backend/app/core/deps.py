import uuid
from collections.abc import AsyncGenerator

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


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    if credentials is None:
        raise unauthorized

    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise unauthorized from exc

    if payload.get("type") != TokenType.ACCESS.value:
        raise unauthorized

    user_id = uuid.UUID(payload["sub"])

    # Scope this request's DB transaction to the caller before any other
    # query runs, so Postgres RLS isolates data even if a query forgets a
    # user_id filter. set_config(..., true) is SET LOCAL semantics (resets at
    # end of transaction) expressed as a function call, since SET LOCAL's
    # own grammar doesn't accept a bind parameter for the value.
    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)})

    user = await db.get(User, user_id)
    if user is None:
        raise unauthorized

    return user

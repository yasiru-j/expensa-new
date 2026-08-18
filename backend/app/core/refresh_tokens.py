import uuid
from datetime import timedelta

from app.core.config import get_settings
from app.core.redis import redis_client

settings = get_settings()


def _key(jti: str) -> str:
    return f"refresh_jti:{jti}"


async def store_refresh_jti(jti: str, user_id: uuid.UUID) -> None:
    await redis_client.set(
        _key(jti), str(user_id), ex=timedelta(days=settings.refresh_token_expire_days)
    )


async def pop_refresh_jti(jti: str) -> str | None:
    """Fetch and delete atomically — a refresh token is single-use."""
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.get(_key(jti))
        pipe.delete(_key(jti))
        user_id, _deleted = await pipe.execute()
    return user_id


async def revoke_refresh_jti(jti: str) -> None:
    await redis_client.delete(_key(jti))

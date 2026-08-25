"""Lazily-created ARQ connection pool for enqueueing jobs from the request
path. A plain module-level constant (like app.core.redis's redis_client)
won't work here — creating an ArqRedis pool is itself an async operation —
so this caches the pool in a module-level variable on first use instead.
Safe under the low concurrency of a first request racing itself: worst case
two pools get created and one is discarded, never a correctness issue."""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import get_settings

settings = get_settings()

_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool

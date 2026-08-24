"""Redis-backed sliding-window rate limiting.

A Lua script makes the whole check-and-record operation a single atomic
round-trip (Redis executes scripts single-threaded), so there's no
check-then-act race between concurrent requests from the same user — unlike
a plain ZCARD-then-ZADD pair issued as two separate commands.
"""

import time
import uuid

from app.core.redis import redis_client

# KEYS[1] = rate limit key
# ARGV[1] = now (seconds, float)
# ARGV[2] = window (seconds)
# ARGV[3] = limit
# ARGV[4] = member (unique per-request; timestamps alone can collide)
_SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)

if count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = window
    if oldest[2] then
        retry_after = math.ceil(window - (now - tonumber(oldest[2])))
    end
    if retry_after < 1 then
        retry_after = 1
    end
    return {0, retry_after}
end

redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, window)
return {1, 0}
"""


async def check_rate_limit(
    user_id: uuid.UUID, action: str, limit: int, window_seconds: int
) -> tuple[bool, int]:
    """Returns (allowed, retry_after_seconds). If allowed, this call has
    already recorded the attempt — don't call it again for the same request."""
    key = f"rate_limit:{action}:{user_id}"
    now = time.time()
    member = f"{now}:{uuid.uuid4()}"

    allowed, retry_after = await redis_client.eval(
        _SLIDING_WINDOW_SCRIPT, 1, key, now, window_seconds, limit, member
    )
    return bool(int(allowed)), int(retry_after)

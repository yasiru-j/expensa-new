"""Runs against the real Redis service — the whole point of the sliding
window is atomicity under concurrency, which a mock can't meaningfully
exercise."""

import asyncio
import uuid

from app.usage.rate_limit import check_rate_limit


async def test_allows_requests_under_the_limit() -> None:
    user_id = uuid.uuid4()

    for _ in range(5):
        allowed, retry_after = await check_rate_limit(
            user_id, "test-action", limit=5, window_seconds=60
        )
        assert allowed is True
        assert retry_after == 0


async def test_blocks_the_request_over_the_limit() -> None:
    user_id = uuid.uuid4()

    for _ in range(3):
        allowed, _ = await check_rate_limit(user_id, "test-action", limit=3, window_seconds=60)
        assert allowed is True

    allowed, retry_after = await check_rate_limit(
        user_id, "test-action", limit=3, window_seconds=60
    )

    assert allowed is False
    assert retry_after > 0


async def test_different_users_have_independent_windows() -> None:
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    for _ in range(3):
        allowed, _ = await check_rate_limit(user_a, "test-action", limit=3, window_seconds=60)
        assert allowed is True

    # user_a is now at the limit; user_b's own window is untouched.
    allowed, _ = await check_rate_limit(user_b, "test-action", limit=3, window_seconds=60)
    assert allowed is True


async def test_different_actions_have_independent_windows() -> None:
    user_id = uuid.uuid4()

    for _ in range(3):
        allowed, _ = await check_rate_limit(user_id, "upload", limit=3, window_seconds=60)
        assert allowed is True

    # Same user, different action key — its own budget.
    allowed, _ = await check_rate_limit(user_id, "other-action", limit=3, window_seconds=60)
    assert allowed is True


async def test_concurrent_requests_at_the_boundary_do_not_over_admit() -> None:
    """The atomic Lua script is what makes this safe — a plain
    read-count-then-write pair issued as two separate Redis commands would
    let concurrent callers both read the same under-limit count and both
    proceed, over-admitting past the limit."""
    user_id = uuid.uuid4()
    limit = 5

    results = await asyncio.gather(
        *[
            check_rate_limit(user_id, "concurrent-test", limit=limit, window_seconds=60)
            for _ in range(10)
        ]
    )

    admitted = sum(1 for allowed, _ in results if allowed)
    assert admitted == limit

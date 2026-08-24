"""Runs against the real Postgres database — the whole point of
try_increment_usage is atomicity under concurrency, which needs a real
database transaction to prove."""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.usage.quota import get_current_usage, try_increment_usage


async def _make_user(owner_session: AsyncSession, email: str) -> uuid.UUID:
    user = User(email=email, password_hash="not-a-real-hash")
    owner_session.add(user)
    await owner_session.commit()
    await owner_session.refresh(user)
    return user.id


async def test_get_current_usage_starts_at_zero(
    owner_session: AsyncSession, app_session_as
) -> None:
    user_id = await _make_user(owner_session, "quota-zero@example.com")

    async with app_session_as(user_id) as session:
        count = await get_current_usage(session, user_id)

    assert count == 0


async def test_increment_succeeds_and_is_reflected_in_get_current_usage(
    owner_session: AsyncSession, app_session_as
) -> None:
    user_id = await _make_user(owner_session, "quota-increment@example.com")

    async with app_session_as(user_id) as session:
        ok = await try_increment_usage(session, user_id)
        assert ok is True

    async with app_session_as(user_id) as session:
        count = await get_current_usage(session, user_id)

    assert count == 1


async def test_increment_fails_once_at_the_limit(
    owner_session: AsyncSession, app_session_as, monkeypatch
) -> None:
    monkeypatch.setattr("app.usage.quota.settings.monthly_extraction_quota", 2)
    user_id = await _make_user(owner_session, "quota-limit@example.com")

    async with app_session_as(user_id) as session:
        assert await try_increment_usage(session, user_id) is True
    async with app_session_as(user_id) as session:
        assert await try_increment_usage(session, user_id) is True
    async with app_session_as(user_id) as session:
        # Third attempt: count is now 2, which is not < 2.
        assert await try_increment_usage(session, user_id) is False

    async with app_session_as(user_id) as session:
        count = await get_current_usage(session, user_id)
    assert count == 2  # the failed attempt did not increment anything


async def test_concurrent_increments_at_cap_minus_one_only_one_succeeds(
    owner_session: AsyncSession, app_session_as, monkeypatch
) -> None:
    monkeypatch.setattr("app.usage.quota.settings.monthly_extraction_quota", 5)
    user_id = await _make_user(owner_session, "quota-race@example.com")

    # Bring the count to exactly one below the cap first.
    async with app_session_as(user_id) as session:
        for _ in range(4):
            assert await try_increment_usage(session, user_id) is True

    async def _attempt() -> bool:
        async with app_session_as(user_id) as session:
            return await try_increment_usage(session, user_id)

    results = await asyncio.gather(*[_attempt() for _ in range(5)])

    assert sum(results) == 1  # exactly one of the five racing attempts won

    async with app_session_as(user_id) as session:
        count = await get_current_usage(session, user_id)
    assert count == 5  # never exceeds the cap

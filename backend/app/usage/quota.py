"""Per-user monthly extraction quota, backed by the `usage` table.

Two distinct mechanisms, deliberately not one:

- get_current_usage(): a cheap, read-only check. Used early in the upload
  flow (right after rate limiting) to fail fast — no point reading/parsing a
  file for a user who's already over quota — but it is NOT the authoritative
  gate, since a plain read-then-act has a race window.
- try_increment_usage(): the authoritative gate. A single atomic SQL
  statement that increments the counter IF AND ONLY IF it's still under the
  limit, and reports back whether it did. Called once, immediately before
  the paid OpenAI call — never on upload-received, never per retry/tier
  within one upload. Two callers racing for the last slot serialize on the
  same row; only one can win.
"""

import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

settings = get_settings()


class QuotaExceededError(Exception):
    """Raised when the atomic increment-and-check finds the caller already
    at their limit — the rare race where an early get_current_usage() check
    passed but a concurrent request consumed the last slot first."""


def current_period() -> date:
    return date.today().replace(day=1)


async def get_current_usage(session: AsyncSession, user_id: uuid.UUID) -> int:
    result = await session.execute(
        text("SELECT extraction_count FROM usage WHERE user_id = :uid AND period_month = :period"),
        {"uid": str(user_id), "period": current_period()},
    )
    row = result.first()
    return row[0] if row else 0


async def try_increment_usage(session: AsyncSession, user_id: uuid.UUID) -> bool:
    """Atomically increments the current period's extraction count if it's
    still under settings.monthly_extraction_quota, in one statement — no
    read-then-write race. Returns whether the increment succeeded (i.e.
    whether the caller may proceed to the paid call)."""
    result = await session.execute(
        text("""
            INSERT INTO usage (user_id, period_month, extraction_count)
            VALUES (:uid, :period, 1)
            ON CONFLICT (user_id, period_month)
            DO UPDATE SET extraction_count = usage.extraction_count + 1
            WHERE usage.extraction_count < :limit
            RETURNING extraction_count
            """),
        {
            "uid": str(user_id),
            "period": current_period(),
            "limit": settings.monthly_extraction_quota,
        },
    )
    return result.first() is not None

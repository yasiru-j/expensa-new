"""Sweeps expenses stuck at status='processing' (a crash between the two
upload transactions, or any other interruption) to 'failed'.

There's no background worker in this app yet — extraction is inline and
synchronous (Phase 2's deliberate choice; the async worker is future work).
Standing up a scheduler for just this one sweep would be a lot of new
infrastructure for a narrow purpose, so this instead runs opportunistically
on read/write paths that already touch a user's expenses: cheap (one indexed
UPDATE), naturally RLS-scoped to the caller's own rows via the request's
existing session, and needs no new process.

The tradeoff: a stuck row for a user who never uploads or lists again stays
stuck indefinitely. Acceptable for now — the natural fix is a periodic job
once a real background worker exists (Phase 6/7), at which point this
function is exactly what that job would call, just on its own schedule
instead of piggybacking on a request.

It's called from two places: upload_expense (so a file stuck at
`processing` doesn't permanently block a fresh retry — the idempotency
unique index treats `processing` as a live, conflicting status) and
list_expenses (so a user browsing sees accurate state rather than a
permanently stuck badge).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

settings = get_settings()


async def sweep_stale_processing_rows(session: AsyncSession) -> int:
    """Flips the caller's own expenses stuck at 'processing' for longer than
    settings.stale_processing_minutes to 'failed'. Returns the row count
    affected. RLS-scoped to whichever user the session's app.user_id is
    currently set to."""
    cutoff = datetime.now(UTC) - timedelta(minutes=settings.stale_processing_minutes)
    result = await session.execute(
        text(
            "UPDATE expenses SET status = 'failed' "
            "WHERE status = 'processing' AND created_at < :cutoff"
        ),
        {"cutoff": cutoff},
    )
    return result.rowcount

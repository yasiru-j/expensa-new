"""app.worker.process_multi_page_pdf, called directly (bypassing the actual
Redis queue — there's no separate worker process running under pytest,
matching how upload_expense's inline path is already tested). Proves the
job persists the same shape of outcome as the inline path, is RLS-scoped
exactly like every other write path (not just trusting its own payload),
and the periodic cross-user sweep works as the worker's cron job will run
it.

The worker calls get_openai_client() as a bare function, not through
FastAPI's dependency-injection system, so the app.dependency_overrides-based
mock_openai_client fixture (used everywhere else in this suite) can't reach
it — these tests monkeypatch app.worker.get_openai_client directly instead.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.maintenance import sweep_all_stale_processing_rows
from app.db.models.expense import Expense
from app.db.models.user import User
from app.storage.s3 import put_object
from app.worker import process_multi_page_pdf
from tests.factories import fake_receipt_response, make_test_pdf_bytes


def _mock_openai(monkeypatch) -> AsyncMock:
    fake_client = AsyncMock()
    monkeypatch.setattr("app.worker.get_openai_client", lambda: fake_client)
    return fake_client


async def _usage_count(app_session_as, user_id) -> int:
    async with app_session_as(user_id) as session:
        row = (
            await session.execute(
                text(
                    "SELECT extraction_count FROM usage "
                    "WHERE user_id = :uid AND period_month = date_trunc('month', now())::date"
                ),
                {"uid": str(user_id)},
            )
        ).first()
    return row[0] if row else 0


async def test_worker_persists_a_ready_expense_on_success(
    client, signup_user, owner_session: AsyncSession, monkeypatch, app_session_as
) -> None:
    fake_client = _mock_openai(monkeypatch)
    token = await signup_user("worker-success@example.com")
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me.json()["id"]

    object_key = f"receipts/{user_id}/multi.pdf"
    await put_object(object_key, make_test_pdf_bytes(pages=2), "application/pdf")

    expense = Expense(user_id=user_id, status="processing", file_url=object_key)
    owner_session.add(expense)
    await owner_session.commit()

    fake_client.chat.completions.create.return_value = fake_receipt_response(vendor="Async Vendor")

    await process_multi_page_pdf({}, str(expense.id), user_id, object_key)

    row = (
        await owner_session.execute(
            text("SELECT status, vendor FROM expenses WHERE id = :id"), {"id": str(expense.id)}
        )
    ).first()
    assert row.status == "ready"
    assert row.vendor == "Async Vendor"
    assert await _usage_count(app_session_as, user_id) == 1


async def test_worker_marks_failed_on_non_receipt(
    client, signup_user, owner_session: AsyncSession, monkeypatch
) -> None:
    fake_client = _mock_openai(monkeypatch)
    token = await signup_user("worker-nonreceipt@example.com")
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me.json()["id"]

    object_key = f"receipts/{user_id}/multi.pdf"
    await put_object(object_key, make_test_pdf_bytes(pages=2), "application/pdf")

    expense = Expense(user_id=user_id, status="processing", file_url=object_key)
    owner_session.add(expense)
    await owner_session.commit()

    fake_client.chat.completions.create.return_value = fake_receipt_response(is_receipt=False)

    await process_multi_page_pdf({}, str(expense.id), user_id, object_key)

    row = (
        await owner_session.execute(
            text("SELECT status FROM expenses WHERE id = :id"), {"id": str(expense.id)}
        )
    ).first()
    assert row.status == "failed"


async def test_worker_never_writes_to_another_users_expense(
    client, signup_user, owner_session: AsyncSession, monkeypatch
) -> None:
    """A hypothetical mismatched (expense_id, user_id) pairing must still be
    blocked by RLS at the worker layer, independent of trusting the enqueue
    call was correct."""
    fake_client = _mock_openai(monkeypatch)
    victim = User(email="worker-victim@example.com", password_hash="not-a-real-hash")
    owner_session.add(victim)
    await owner_session.flush()
    victim_expense = Expense(user_id=victim.id, status="processing", vendor=None)
    owner_session.add(victim_expense)
    await owner_session.commit()

    attacker_token = await signup_user("worker-attacker@example.com")
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {attacker_token}"})
    attacker_id = me.json()["id"]

    fake_client.chat.completions.create.return_value = fake_receipt_response(
        vendor="Should Never Land"
    )

    # object_key doesn't need to resolve to anything real — get_object fails
    # first, landing the (nonexistent, from this attacker's RLS-scoped view)
    # row at "failed", which is itself the point: the attacker's session
    # can't even see the victim's row to flip it.
    await process_multi_page_pdf(
        {}, str(victim_expense.id), attacker_id, "receipts/nonexistent/x.pdf"
    )

    row = (
        await owner_session.execute(
            text("SELECT status, vendor FROM expenses WHERE id = :id"),
            {"id": str(victim_expense.id)},
        )
    ).first()
    assert row.status == "processing"  # untouched
    assert row.vendor is None


async def test_worker_handles_a_row_deleted_before_the_job_ran(
    client, signup_user, monkeypatch
) -> None:
    """The user (or their whole account) may have deleted the expense while
    an async job for it was still in flight — the job must not crash."""
    _mock_openai(monkeypatch)
    token = await signup_user("worker-deleted-row@example.com")
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me.json()["id"]

    await process_multi_page_pdf({}, str(uuid.uuid4()), user_id, "receipts/nonexistent/gone.pdf")
    # No exception raised is the assertion.


async def test_periodic_sweep_flips_stale_rows_across_multiple_users(
    owner_session: AsyncSession,
) -> None:
    user_a = User(email="sweep-a@example.com", password_hash="not-a-real-hash")
    user_b = User(email="sweep-b@example.com", password_hash="not-a-real-hash")
    owner_session.add_all([user_a, user_b])
    await owner_session.flush()

    stale_a = Expense(
        user_id=user_a.id,
        status="processing",
        created_at=datetime.now(UTC) - timedelta(minutes=999),
    )
    stale_b = Expense(
        user_id=user_b.id,
        status="processing",
        created_at=datetime.now(UTC) - timedelta(minutes=999),
    )
    fresh = Expense(user_id=user_a.id, status="processing")
    owner_session.add_all([stale_a, stale_b, fresh])
    await owner_session.commit()

    swept = await sweep_all_stale_processing_rows(owner_session)
    await owner_session.commit()

    assert swept == 2

    rows = (
        await owner_session.execute(
            text("SELECT id, status FROM expenses WHERE id = ANY(:ids)"),
            {"ids": [str(stale_a.id), str(stale_b.id), str(fresh.id)]},
        )
    ).all()
    status_by_id = {str(r.id): r.status for r in rows}
    assert status_by_id[str(stale_a.id)] == "failed"
    assert status_by_id[str(stale_b.id)] == "failed"
    assert status_by_id[str(fresh.id)] == "processing"

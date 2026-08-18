"""
Proves tenant isolation holds at the database layer, independent of the API.

Every query below runs as the restricted `expensa_app` role — the same role
the FastAPI backend connects as — with `SET LOCAL app.user_id` set exactly
the way `get_current_user` sets it per request. None of these queries add an
explicit `WHERE user_id = ...` filter: if RLS were misconfigured (missing
FORCE, wrong policy, app connecting as the table owner), these would fail.
"""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.expense import Expense
from app.db.models.user import User


async def _make_user(owner_session: AsyncSession, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash")
    owner_session.add(user)
    await owner_session.commit()
    await owner_session.refresh(user)
    return user


async def test_user_cannot_read_another_users_expense_without_a_filter(
    owner_session: AsyncSession, app_session_as
) -> None:
    user_a = await _make_user(owner_session, "user-a@example.com")
    user_b = await _make_user(owner_session, "user-b@example.com")

    async with app_session_as(user_a.id) as session:
        session.add(Expense(user_id=user_a.id, vendor="A's Vendor", status="pending"))
        await session.flush()

    # No WHERE user_id = ... anywhere here — RLS alone must do the isolating.
    async with app_session_as(user_b.id) as session:
        rows = (await session.execute(select(Expense))).scalars().all()
        assert rows == []

    # Sanity check: the owner can see their own row, so isolation isn't just
    # "nobody can see anything."
    async with app_session_as(user_a.id) as session:
        rows = (await session.execute(select(Expense))).scalars().all()
        assert len(rows) == 1
        assert rows[0].vendor == "A's Vendor"


async def test_user_cannot_update_or_delete_another_users_expense(
    owner_session: AsyncSession, app_session_as
) -> None:
    user_a = await _make_user(owner_session, "user-a2@example.com")
    user_b = await _make_user(owner_session, "user-b2@example.com")

    async with app_session_as(user_a.id) as session:
        expense = Expense(user_id=user_a.id, vendor="A's Vendor", status="pending")
        session.add(expense)
        await session.flush()
        expense_id = expense.id

    async with app_session_as(user_b.id) as session:
        update_result = await session.execute(
            text("UPDATE expenses SET vendor = 'Hijacked' WHERE id = :id"),
            {"id": str(expense_id)},
        )
        assert update_result.rowcount == 0

        delete_result = await session.execute(
            text("DELETE FROM expenses WHERE id = :id"), {"id": str(expense_id)}
        )
        assert delete_result.rowcount == 0

    async with app_session_as(user_a.id) as session:
        untouched = await session.get(Expense, expense_id)
        assert untouched is not None
        assert untouched.vendor == "A's Vendor"


async def test_user_cannot_insert_a_row_claiming_another_users_id(
    owner_session: AsyncSession, app_session_as
) -> None:
    user_a = await _make_user(owner_session, "user-a3@example.com")
    user_b = await _make_user(owner_session, "user-b3@example.com")

    # Authenticated as B, but the row claims to belong to A — WITH CHECK must
    # reject it. Unlike SELECT/UPDATE/DELETE (which just filter rows), a
    # WITH CHECK violation on INSERT raises rather than silently no-opping.
    async with app_session_as(user_b.id) as session:
        with pytest.raises(DBAPIError, match="row-level security"):
            await session.execute(
                text(
                    "INSERT INTO expenses (user_id, vendor, status) "
                    "VALUES (:user_id, 'Spoofed', 'pending')"
                ),
                {"user_id": str(user_a.id)},
            )


async def test_no_session_variable_set_yields_no_rows(
    owner_session: AsyncSession, app_session_as
) -> None:
    user_a = await _make_user(owner_session, "user-a4@example.com")

    async with app_session_as(user_a.id) as session:
        session.add(Expense(user_id=user_a.id, vendor="A's Vendor", status="pending"))
        await session.flush()

    # No SET LOCAL app.user_id at all: current_setting(..., true) is NULL,
    # and "user_id = NULL" is never true, so this must also see zero rows.
    async with app_session_as(None) as session:
        rows = (await session.execute(select(Expense))).scalars().all()
        assert rows == []


async def test_line_items_inherit_isolation_from_parent_expense(
    owner_session: AsyncSession, app_session_as
) -> None:
    user_a = await _make_user(owner_session, "user-a5@example.com")
    user_b = await _make_user(owner_session, "user-b5@example.com")

    async with app_session_as(user_a.id) as session:
        expense = Expense(user_id=user_a.id, vendor="A's Vendor", status="pending")
        session.add(expense)
        await session.flush()
        await session.execute(
            text(
                "INSERT INTO line_items (expense_id, description, amount) "
                "VALUES (:expense_id, 'Widget', 9.99)"
            ),
            {"expense_id": str(expense.id)},
        )

    async with app_session_as(user_b.id) as session:
        rows = (await session.execute(text("SELECT * FROM line_items"))).fetchall()
        assert rows == []

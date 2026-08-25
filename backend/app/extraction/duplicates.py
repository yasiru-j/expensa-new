"""Duplicate-receipt detection: flags an expense as a potential duplicate
when another expense for the same user shares vendor + expense_date + total.
This is a WARNING surfaced to the user (table row badge, review banner),
never a block — the user decides whether it's a genuine re-upload or a
second, legitimately identical purchase.

Rows missing any of the three fields (extraction not complete, or the user
cleared one) are never flagged — comparing on NULL would otherwise group
every not-yet-extracted row together as "duplicates" of each other.

Two entry points, which must stay semantically identical:
- duplicate_flag_expression(): a SQL expression for bulk list queries.
- is_potential_duplicate(): a plain query for a single already-loaded row.
"""

from sqlalchemy import ColumnElement, and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models.expense import Expense

_Other = aliased(Expense)


def duplicate_flag_expression() -> ColumnElement[bool]:
    """A boolean column usable alongside select(Expense, ...) in a bulk
    query — True when another row (any status) shares this row's
    vendor/expense_date/total.

    No explicit user_id equality condition — like the rest of this API,
    isolation is left entirely to Postgres RLS, which already scopes every
    reference to `expenses` (including this correlated subquery) to the
    caller's own rows.
    """
    has_comparable_fields = and_(
        Expense.vendor.is_not(None),
        Expense.expense_date.is_not(None),
        Expense.total.is_not(None),
    )
    other_match_exists = (
        select(func.count())
        .select_from(_Other)
        .where(
            _Other.id != Expense.id,
            _Other.vendor == Expense.vendor,
            _Other.expense_date == Expense.expense_date,
            _Other.total == Expense.total,
        )
        .correlate(Expense)
        .scalar_subquery()
        > 0
    )
    return case((has_comparable_fields, other_match_exists), else_=False)


async def is_potential_duplicate(db: AsyncSession, expense: Expense) -> bool:
    """Single-row variant for call sites that already have one Expense
    loaded (get/update/confirm) rather than running a bulk list query."""
    if expense.vendor is None or expense.expense_date is None or expense.total is None:
        return False
    count = await db.scalar(
        select(func.count())
        .select_from(Expense)
        .where(
            Expense.id != expense.id,
            Expense.vendor == expense.vendor,
            Expense.expense_date == expense.expense_date,
            Expense.total == expense.total,
        )
    )
    return bool(count)

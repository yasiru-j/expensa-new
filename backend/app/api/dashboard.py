from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.db.models.expense import Expense
from app.db.models.user import User
from app.schemas.dashboard import (
    CategoryBreakdown,
    CurrencyAmount,
    DashboardSummary,
    MonthlyBreakdown,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _or_zero(total: Decimal | None) -> Decimal:
    # `total or 0` would be wrong here: Decimal("0.00") is falsy in Python,
    # so a group whose rows genuinely sum to zero would fall through to a
    # bare int too — harmless once Pydantic re-coerces it, but worth being
    # explicit about rather than relying on that.
    return total if total is not None else Decimal("0")


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


def _first_of_next_month(d: date) -> date:
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1, day=1)
    return d.replace(month=d.month + 1, day=1)


def _months_ago(base: date, months: int) -> date:
    """First day of the month that is `months` calendar months before base
    (0 = the month base itself falls in)."""
    month_index = base.month - 1 - months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    months: int = Query(12, ge=1, le=24),
) -> DashboardSummary:
    """Aggregates over CONFIRMED expenses only — "only confirmed rows count
    as final" (Phase 3's ready-review loop). Everything is computed in SQL
    (GROUP BY), never by pulling rows and summing in Python, and every
    aggregate groups by currency alongside its own dimension so amounts are
    never summed across different currencies into one number.

    month_to_date is scoped to the current calendar month; by_category and
    receipt_count are all-time; by_month is windowed to the last `months`
    calendar months (default 12) so the series stays bounded. Rows with no
    expense_date (extraction couldn't determine one, and it was never
    corrected) are excluded from month_to_date and by_month — there's no
    month to attribute them to — but still count toward by_category and
    receipt_count.
    """
    today = date.today()
    month_start = _first_of_month(today)
    next_month_start = _first_of_next_month(today)
    window_start = _months_ago(today, months - 1)

    confirmed = Expense.status == "confirmed"

    mtd_rows = (
        await db.execute(
            select(Expense.currency, func.sum(Expense.total))
            .where(confirmed)
            .where(Expense.expense_date >= month_start)
            .where(Expense.expense_date < next_month_start)
            .group_by(Expense.currency)
        )
    ).all()

    receipt_count = await db.scalar(select(func.count()).select_from(Expense).where(confirmed))

    category_rows = (
        await db.execute(
            select(Expense.category, Expense.currency, func.sum(Expense.total), func.count())
            .where(confirmed)
            .group_by(Expense.category, Expense.currency)
            .order_by(Expense.category)
        )
    ).all()

    month_expr = func.to_char(Expense.expense_date, "YYYY-MM")
    month_rows = (
        await db.execute(
            select(month_expr, Expense.currency, func.sum(Expense.total))
            .where(confirmed)
            .where(Expense.expense_date.is_not(None))
            .where(Expense.expense_date >= window_start)
            .group_by(month_expr, Expense.currency)
            .order_by(month_expr)
        )
    ).all()

    return DashboardSummary(
        month_to_date=[
            CurrencyAmount(currency=currency, total=_or_zero(total)) for currency, total in mtd_rows
        ],
        receipt_count=receipt_count or 0,
        by_category=[
            CategoryBreakdown(
                category=category, currency=currency, total=_or_zero(total), count=count
            )
            for category, currency, total, count in category_rows
        ],
        by_month=[
            MonthlyBreakdown(month=month, currency=currency, total=_or_zero(total))
            for month, currency, total in month_rows
        ],
    )

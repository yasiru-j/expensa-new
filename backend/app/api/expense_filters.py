"""Filter-building shared by GET /api/expenses and GET /api/export, so the
two endpoints can never drift apart on what a given set of query params
matches — both build their WHERE clause from build_expense_conditions."""

from datetime import date as date_type

from sqlalchemy import ColumnElement

from app.db.models.expense import STATUSES, Expense
from app.extraction.schema import CATEGORIES

STATUS_PATTERN = f"^({'|'.join(STATUSES)})$"
CATEGORY_PATTERN = f"^({'|'.join(CATEGORIES)})$"

SORT_OPTIONS = {
    "date_desc": Expense.expense_date.desc().nulls_last(),
    "date_asc": Expense.expense_date.asc().nulls_last(),
    "created_desc": Expense.created_at.desc(),
    "created_asc": Expense.created_at.asc(),
}
SORT_PATTERN = f"^({'|'.join(SORT_OPTIONS)})$"


def escape_like(value: str) -> str:
    """Escapes LIKE/ILIKE wildcard characters in free-text user input, so a
    vendor search for e.g. "50% off" doesn't have the % treated as a
    wildcard."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_expense_conditions(
    *,
    status_filter: str | None,
    date_from: date_type | None,
    date_to: date_type | None,
    category: str | None,
    q: str | None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if status_filter is not None:
        conditions.append(Expense.status == status_filter)
    if date_from is not None:
        conditions.append(Expense.expense_date >= date_from)
    if date_to is not None:
        conditions.append(Expense.expense_date <= date_to)
    if category is not None:
        conditions.append(Expense.category == category)
    if q:
        conditions.append(Expense.vendor.ilike(f"%{escape_like(q)}%", escape="\\"))
    return conditions

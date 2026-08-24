from decimal import Decimal

from pydantic import BaseModel


class CurrencyAmount(BaseModel):
    currency: str | None
    total: Decimal


class CategoryBreakdown(BaseModel):
    category: str
    currency: str | None
    total: Decimal
    count: int


class MonthlyBreakdown(BaseModel):
    month: str  # "YYYY-MM"
    currency: str | None
    total: Decimal


class DashboardSummary(BaseModel):
    """Every aggregate here is grouped by currency as well as its own
    dimension — a user with both AUD and USD receipts never gets one number
    that silently sums the two together."""

    month_to_date: list[CurrencyAmount]
    receipt_count: int
    by_category: list[CategoryBreakdown]
    by_month: list[MonthlyBreakdown]

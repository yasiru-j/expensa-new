import re
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.extraction.schema import CATEGORIES

_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")


class ExpenseUploadResponse(BaseModel):
    id: uuid.UUID
    status: str


class LineItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    description: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    amount: Decimal | None


class ExpenseListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vendor: str | None
    expense_date: date | None
    total: Decimal | None
    currency: str | None
    category: str | None
    status: str
    extracted_confidence: Decimal | None
    created_at: datetime


class ExpenseRead(ExpenseListItem):
    vendor_tax_id: str | None
    subtotal: Decimal | None
    tax: Decimal | None
    payment_method: str | None
    updated_at: datetime
    line_items: list[LineItemRead]
    file_url: str | None = None  # short-lived presigned GET URL, generated per request
    field_provenance: dict[str, dict]


class PaginatedExpenses(BaseModel):
    items: list[ExpenseListItem]
    total: int
    page: int
    page_size: int


class ExpensePatchRequest(BaseModel):
    """All fields optional; only the ones actually present in the request body
    (per model_fields_set / exclude_unset) are treated as edits — this is
    what distinguishes "not sent" from "explicitly cleared to null"."""

    vendor: str | None = None
    vendor_tax_id: str | None = None
    expense_date: date | None = None
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None
    currency: str | None = None
    category: str | None = None
    payment_method: str | None = None

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _CURRENCY_RE.match(value.strip()):
            raise ValueError("currency must be a 3-letter ISO 4217 code, e.g. AUD")
        return value.strip().upper()

    @field_validator("category")
    @classmethod
    def _validate_category(cls, value: str | None) -> str | None:
        if value is not None and value not in CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(CATEGORIES)}")
        return value

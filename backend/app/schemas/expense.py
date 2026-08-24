import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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


class PaginatedExpenses(BaseModel):
    items: list[ExpenseListItem]
    total: int
    page: int
    page_size: int

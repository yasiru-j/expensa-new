import re
from dataclasses import dataclass, field
from datetime import date as date_type
from decimal import Decimal

from app.extraction.schema import CATEGORIES, ReceiptExtraction

ARITHMETIC_TOLERANCE = Decimal("0.05")
DEFAULT_CURRENCY = "AUD"
LOW_CONFIDENCE_CAP = Decimal("0.400")
_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")


@dataclass
class ValidatedLineItem:
    description: str
    quantity: Decimal | None
    unit_price: Decimal | None
    amount: Decimal | None


@dataclass
class ValidatedExpense:
    vendor: str | None
    vendor_tax_id: str | None
    expense_date: date_type | None
    subtotal: Decimal | None
    tax: Decimal | None
    total: Decimal | None
    currency: str
    category: str
    payment_method: str | None
    confidence: Decimal
    line_items: list[ValidatedLineItem] = field(default_factory=list)


def _normalize_date(raw: str | None) -> date_type | None:
    if not raw:
        return None
    try:
        return date_type.fromisoformat(raw.strip())
    except ValueError:
        return None


def _normalize_currency(raw: str | None) -> str:
    if raw and _CURRENCY_RE.match(raw.strip()):
        return raw.strip().upper()
    return DEFAULT_CURRENCY


def _normalize_category(raw: str | None) -> str:
    return raw if raw in CATEGORIES else "Other"


def validate_and_normalize(data: ReceiptExtraction) -> ValidatedExpense:
    """Normalizes a successfully-parsed extraction into DB-ready fields.

    Per TRD §5.4, arithmetic mismatches, unparseable dates, and unrecognized
    currency/category are *soft* issues: normalized or nulled where safe,
    confidence lowered, and the row still proceeds to `ready` for human review
    in Phase 3. Only `is_receipt=false` is a hard rejection, and that's handled
    upstream in the service layer before this function is ever called.
    """
    confidence = Decimal(str(data.confidence)).quantize(Decimal("0.001"))

    if data.subtotal is not None and data.tax is not None and data.total is not None:
        expected_total = data.subtotal + data.tax
        if abs(expected_total - data.total) > ARITHMETIC_TOLERANCE:
            confidence = min(confidence, LOW_CONFIDENCE_CAP)

    return ValidatedExpense(
        vendor=data.vendor,
        vendor_tax_id=data.vendor_tax_id,
        expense_date=_normalize_date(data.date),
        subtotal=data.subtotal,
        tax=data.tax,
        total=data.total,
        currency=_normalize_currency(data.currency),
        category=_normalize_category(data.category),
        payment_method=data.payment_method,
        confidence=confidence,
        line_items=[
            ValidatedLineItem(
                description=li.description,
                quantity=li.quantity,
                unit_price=li.unit_price,
                amount=li.amount,
            )
            for li in data.line_items
        ],
    )

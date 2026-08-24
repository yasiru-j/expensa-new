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
    """Overall row-level confidence — lowered if ANY field below was flagged.
    Drives the `expenses.extracted_confidence` column, which is what a table
    view uses to flag a whole row for review at a glance."""
    raw_confidence: Decimal
    """The model's own self-reported confidence, never lowered. We don't have
    genuine per-field confidence from the model — only one overall number —
    so this is what gets stored in every field's provenance entry; the
    `field_flags` below are the real per-field signal."""
    field_flags: dict[str, list[str]] = field(default_factory=dict)
    line_items: list[ValidatedLineItem] = field(default_factory=list)


def _normalize_date(raw: str | None) -> tuple[date_type | None, bool]:
    """Returns (value, was_invalid). A missing date isn't invalid — there was
    just nothing to parse."""
    if not raw:
        return None, False
    try:
        return date_type.fromisoformat(raw.strip()), False
    except ValueError:
        return None, True


def _normalize_currency(raw: str | None) -> tuple[str, bool]:
    if not raw:
        return DEFAULT_CURRENCY, False
    if _CURRENCY_RE.match(raw.strip()):
        return raw.strip().upper(), False
    return DEFAULT_CURRENCY, True


def _normalize_category(raw: str | None) -> tuple[str, bool]:
    if not raw:
        return "Other", False
    if raw in CATEGORIES:
        return raw, False
    return "Other", True


def validate_and_normalize(data: ReceiptExtraction) -> ValidatedExpense:
    """Normalizes a successfully-parsed extraction into DB-ready fields.

    Per TRD §5.4, arithmetic mismatches, unparseable dates, and unrecognized
    currency/category are *soft* issues: normalized or nulled where safe,
    confidence lowered, and the row still proceeds to `ready` for human review
    in Phase 3. Only `is_receipt=false` is a hard rejection, and that's handled
    upstream in the service layer before this function is ever called.

    Each soft issue also records WHICH field(s) tripped it, in field_flags —
    Phase 3's review UI uses this to highlight precisely rather than dimming
    the whole row.
    """
    raw_confidence = Decimal(str(data.confidence)).quantize(Decimal("0.001"))
    confidence = raw_confidence
    field_flags: dict[str, list[str]] = {}

    def _flag(field_name: str, reason: str) -> None:
        nonlocal confidence
        field_flags.setdefault(field_name, []).append(reason)
        confidence = min(confidence, LOW_CONFIDENCE_CAP)

    if data.subtotal is not None and data.tax is not None and data.total is not None:
        expected_total = data.subtotal + data.tax
        if abs(expected_total - data.total) > ARITHMETIC_TOLERANCE:
            # Any of the three could be the culprit — flag all of them so the
            # reviewer checks the actual math, not a guessed single field.
            for f in ("subtotal", "tax", "total"):
                _flag(f, "arithmetic_mismatch")

    expense_date, date_invalid = _normalize_date(data.date)
    if date_invalid:
        _flag("expense_date", "unparseable_date")

    currency, currency_invalid = _normalize_currency(data.currency)
    if currency_invalid:
        _flag("currency", "invalid_currency")

    category, category_invalid = _normalize_category(data.category)
    if category_invalid:
        _flag("category", "unknown_category")

    return ValidatedExpense(
        vendor=data.vendor,
        vendor_tax_id=data.vendor_tax_id,
        expense_date=expense_date,
        subtotal=data.subtotal,
        tax=data.tax,
        total=data.total,
        currency=currency,
        category=category,
        payment_method=data.payment_method,
        confidence=confidence,
        raw_confidence=raw_confidence,
        field_flags=field_flags,
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

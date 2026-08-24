from decimal import Decimal

from app.extraction.schema import LineItemExtraction, ReceiptExtraction
from app.extraction.validation import DEFAULT_CURRENCY, LOW_CONFIDENCE_CAP, validate_and_normalize


def _extraction(**overrides) -> ReceiptExtraction:
    defaults = {
        "is_receipt": True,
        "vendor": "Corner Cafe",
        "vendor_tax_id": None,
        "date": "2026-03-14",
        "currency": "aud",
        "subtotal": Decimal("20.00"),
        "tax": Decimal("2.00"),
        "total": Decimal("22.00"),
        "payment_method": "card",
        "category": "Meals",
        "line_items": [],
        "confidence": 0.9,
    }
    defaults.update(overrides)
    return ReceiptExtraction(**defaults)


def test_arithmetic_within_tolerance_keeps_confidence() -> None:
    result = validate_and_normalize(
        _extraction(subtotal=Decimal("20.00"), tax=Decimal("2.00"), total=Decimal("22.00"))
    )

    assert result.confidence == Decimal("0.900")


def test_arithmetic_mismatch_lowers_confidence_but_still_proceeds() -> None:
    # Off by $5 — well past the rounding tolerance.
    result = validate_and_normalize(
        _extraction(subtotal=Decimal("20.00"), tax=Decimal("2.00"), total=Decimal("27.00"))
    )

    assert result.confidence <= LOW_CONFIDENCE_CAP
    # Soft-flag per TRD §5.4: the row is still fully populated, not rejected.
    assert result.total == Decimal("27.00")
    assert result.subtotal == Decimal("20.00")


def test_arithmetic_within_rounding_tolerance_is_not_flagged() -> None:
    result = validate_and_normalize(
        _extraction(subtotal=Decimal("20.00"), tax=Decimal("2.00"), total=Decimal("22.03"))
    )

    assert result.confidence == Decimal("0.900")


def test_missing_totals_skip_arithmetic_check() -> None:
    result = validate_and_normalize(
        _extraction(subtotal=None, tax=Decimal("2.00"), total=Decimal("22.00"))
    )

    assert result.confidence == Decimal("0.900")


def test_valid_iso_date_is_parsed() -> None:
    result = validate_and_normalize(_extraction(date="2026-03-14"))

    assert result.expense_date is not None
    assert result.expense_date.isoformat() == "2026-03-14"


def test_unparseable_date_is_nulled_not_rejected() -> None:
    result = validate_and_normalize(_extraction(date="14th of March"))

    assert result.expense_date is None


def test_missing_date_is_nulled() -> None:
    result = validate_and_normalize(_extraction(date=None))

    assert result.expense_date is None


def test_valid_currency_is_uppercased() -> None:
    result = validate_and_normalize(_extraction(currency="aud"))

    assert result.currency == "AUD"


def test_invalid_currency_defaults_to_aud() -> None:
    result = validate_and_normalize(_extraction(currency="not-a-code"))

    assert result.currency == DEFAULT_CURRENCY


def test_missing_currency_defaults_to_aud() -> None:
    result = validate_and_normalize(_extraction(currency=None))

    assert result.currency == DEFAULT_CURRENCY


def test_known_category_is_kept() -> None:
    result = validate_and_normalize(_extraction(category="Software"))

    assert result.category == "Software"


def test_unknown_category_defaults_to_other() -> None:
    result = validate_and_normalize(_extraction(category="Groceries"))

    assert result.category == "Other"


def test_missing_category_defaults_to_other() -> None:
    result = validate_and_normalize(_extraction(category=None))

    assert result.category == "Other"


def test_line_items_are_carried_through() -> None:
    result = validate_and_normalize(
        _extraction(
            line_items=[
                LineItemExtraction(
                    description="Coffee",
                    quantity=Decimal("2"),
                    unit_price=Decimal("5.00"),
                    amount=Decimal("10.00"),
                )
            ]
        )
    )

    assert len(result.line_items) == 1
    assert result.line_items[0].description == "Coffee"
    assert result.line_items[0].amount == Decimal("10.00")

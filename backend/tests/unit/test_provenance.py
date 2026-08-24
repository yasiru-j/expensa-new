from decimal import Decimal

from app.extraction.provenance import PROVENANCE_FIELDS, apply_user_edits, build_initial_provenance
from app.extraction.validation import ValidatedExpense


def _validated(**overrides) -> ValidatedExpense:
    defaults = dict(
        vendor="Corner Cafe",
        vendor_tax_id="12 345 678 901",
        expense_date=None,
        subtotal=Decimal("20.00"),
        tax=Decimal("2.00"),
        total=Decimal("22.00"),
        currency="AUD",
        category="Meals",
        payment_method="card",
        confidence=Decimal("0.400"),
        raw_confidence=Decimal("0.950"),
        field_flags={"total": ["arithmetic_mismatch"]},
    )
    defaults.update(overrides)
    return ValidatedExpense(**defaults)


def test_build_initial_provenance_covers_every_tracked_field() -> None:
    provenance = build_initial_provenance(_validated())

    assert set(provenance.keys()) == set(PROVENANCE_FIELDS)


def test_build_initial_provenance_sources_every_field_as_ai() -> None:
    provenance = build_initial_provenance(_validated())

    assert all(entry["source"] == "ai" for entry in provenance.values())


def test_build_initial_provenance_uses_raw_confidence_not_lowered_confidence() -> None:
    provenance = build_initial_provenance(_validated())

    # confidence=0.400 (lowered) vs raw_confidence=0.950 (the model's own
    # number) — every field's provenance entry carries the raw one, since
    # that's the actual signal for "how sure was the model about THIS value."
    assert provenance["vendor"]["confidence"] == 0.950


def test_build_initial_provenance_carries_ai_value() -> None:
    provenance = build_initial_provenance(_validated(vendor="Corner Cafe"))

    assert provenance["vendor"]["ai_value"] == "Corner Cafe"


def test_build_initial_provenance_serializes_decimal_and_date_as_strings() -> None:
    import datetime

    provenance = build_initial_provenance(
        _validated(total=Decimal("22.00"), expense_date=datetime.date(2026, 3, 14))
    )

    assert provenance["total"]["ai_value"] == "22.00"
    assert provenance["expense_date"]["ai_value"] == "2026-03-14"


def test_build_initial_provenance_carries_flags_only_for_flagged_fields() -> None:
    provenance = build_initial_provenance(
        _validated(field_flags={"total": ["arithmetic_mismatch"]})
    )

    assert provenance["total"]["flags"] == ["arithmetic_mismatch"]
    assert "flags" not in provenance["vendor"]


def test_apply_user_edits_flips_only_changed_fields_to_user() -> None:
    provenance = build_initial_provenance(_validated())

    updated = apply_user_edits(provenance, {"vendor"})

    assert updated["vendor"]["source"] == "user"
    assert updated["total"]["source"] == "ai"


def test_apply_user_edits_preserves_ai_value_and_flags() -> None:
    provenance = build_initial_provenance(
        _validated(field_flags={"total": ["arithmetic_mismatch"]})
    )

    updated = apply_user_edits(provenance, {"total"})

    assert updated["total"]["source"] == "user"
    assert updated["total"]["ai_value"] == "22.00"
    assert updated["total"]["flags"] == ["arithmetic_mismatch"]


def test_apply_user_edits_on_a_field_missing_from_provenance_still_works() -> None:
    # e.g. a pre-migration row backfilled to field_provenance = {}
    updated = apply_user_edits({}, {"vendor"})

    assert updated["vendor"]["source"] == "user"
    assert updated["vendor"]["ai_value"] is None


def test_apply_user_edits_does_not_mutate_the_input_dict() -> None:
    provenance = build_initial_provenance(_validated())
    original_source = provenance["vendor"]["source"]

    apply_user_edits(provenance, {"vendor"})

    assert provenance["vendor"]["source"] == original_source

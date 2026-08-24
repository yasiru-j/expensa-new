"""Builds and updates the `expenses.field_provenance` JSONB column.

Shape: { field_name: { source: "ai"|"user", ai_value: <original>, confidence: <num|null>,
                        flags?: [str] } }
"""

from datetime import date as date_type
from decimal import Decimal
from typing import Any

from app.extraction.validation import ValidatedExpense

# The scalar, individually-editable fields tracked in field_provenance.
# line_items are a list, not a single value, and stay out of per-field
# provenance tracking for this phase — they're read-only in the review UI.
PROVENANCE_FIELDS = (
    "vendor",
    "vendor_tax_id",
    "expense_date",
    "subtotal",
    "tax",
    "total",
    "currency",
    "category",
    "payment_method",
)

EMPTY_PROVENANCE_ENTRY: dict[str, Any] = {"source": "ai", "ai_value": None, "confidence": None}


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date_type):
        return value.isoformat()
    return value


def build_initial_provenance(validated: ValidatedExpense) -> dict[str, dict]:
    """Called once, right after a successful extraction — every field starts
    out AI-sourced, carrying the model's own value and the (unlowered)
    self-reported confidence, plus any validation flags raised for it."""
    provenance: dict[str, dict] = {}
    for name in PROVENANCE_FIELDS:
        entry: dict[str, Any] = {
            "source": "ai",
            "ai_value": _jsonable(getattr(validated, name)),
            "confidence": float(validated.raw_confidence),
        }
        flags = validated.field_flags.get(name)
        if flags:
            entry["flags"] = flags
        provenance[name] = entry
    return provenance


def apply_user_edits(provenance: dict[str, dict], changed_fields: set[str]) -> dict[str, dict]:
    """Flips provenance to source="user" for each changed field, preserving
    ai_value (and any flags) so the original AI answer is never lost."""
    updated = {**provenance}
    for name in changed_fields:
        entry = dict(updated.get(name) or EMPTY_PROVENANCE_ENTRY)
        entry["source"] = "user"
        updated[name] = entry
    return updated

"""Writes the final state of one expense row after an extraction attempt —
shared between the inline (single-page) upload path and the async worker
(multi-page PDFs) so the two can't drift on what "done" means for a row.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.expense import Expense
from app.db.models.line_item import LineItem
from app.extraction.provenance import build_initial_provenance
from app.extraction.validation import ValidatedExpense


async def persist_extraction_outcome(
    session: AsyncSession, expense_id: uuid.UUID, validated: ValidatedExpense | None
) -> str | None:
    """validated=None means extraction failed (or never ran) — the row lands
    at status='failed'. Otherwise every extracted field, its provenance, and
    any line items are written and the row lands at status='ready'.

    Returns the resulting status, or None if the row no longer exists (e.g.
    the user deleted this expense, or their whole account, while an async
    worker job for it was still in flight) — nothing to persist in that case.
    """
    expense = await session.get(Expense, expense_id)
    if expense is None:
        return None

    if validated is None:
        expense.status = "failed"
    else:
        expense.vendor = validated.vendor
        expense.vendor_tax_id = validated.vendor_tax_id
        expense.expense_date = validated.expense_date
        expense.subtotal = validated.subtotal
        expense.tax = validated.tax
        expense.total = validated.total
        expense.currency = validated.currency
        expense.category = validated.category
        expense.payment_method = validated.payment_method
        expense.extracted_confidence = validated.confidence
        expense.field_provenance = build_initial_provenance(validated)
        expense.status = "ready"
        for li in validated.line_items:
            session.add(
                LineItem(
                    expense_id=expense.id,
                    description=li.description,
                    quantity=li.quantity,
                    unit_price=li.unit_price,
                    amount=li.amount,
                )
            )

    await session.flush()
    return expense.status

from decimal import Decimal

from pydantic import BaseModel, Field

CATEGORIES = (
    "Meals",
    "Travel",
    "Office Supplies",
    "Software",
    "Utilities",
    "Professional Services",
    "Other",
)


class LineItemExtraction(BaseModel):
    description: str
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None


class ReceiptExtraction(BaseModel):
    """Mirrors the TRD §5.3 extraction contract exactly.

    `date`, `currency`, and `category` are kept as raw strings here rather than
    strict/enum types: a model response with a slightly malformed date or an
    off-taxonomy category should be normalized or nulled by the validation
    layer, not blow up JSON parsing for the whole extraction.
    """

    is_receipt: bool
    vendor: str | None = None
    vendor_tax_id: str | None = None
    date: str | None = None
    currency: str | None = None
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None
    payment_method: str | None = None
    category: str | None = None
    line_items: list[LineItemExtraction] = Field(default_factory=list)
    confidence: float = 0.0


RECEIPT_JSON_SCHEMA: dict = {
    "name": "receipt_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "is_receipt": {"type": "boolean"},
            "vendor": {"type": ["string", "null"]},
            "vendor_tax_id": {"type": ["string", "null"]},
            "date": {"type": ["string", "null"], "description": "YYYY-MM-DD if known"},
            "currency": {"type": ["string", "null"], "description": "ISO 4217 code, e.g. AUD"},
            "subtotal": {"type": ["number", "null"]},
            "tax": {"type": ["number", "null"]},
            "total": {"type": ["number", "null"]},
            "payment_method": {"type": ["string", "null"]},
            "category": {"type": ["string", "null"], "enum": [*CATEGORIES, None]},
            "line_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "description": {"type": "string"},
                        "quantity": {"type": ["number", "null"]},
                        "unit_price": {"type": ["number", "null"]},
                        "amount": {"type": ["number", "null"]},
                    },
                    "required": ["description", "quantity", "unit_price", "amount"],
                },
            },
            "confidence": {"type": "number"},
        },
        "required": [
            "is_receipt",
            "vendor",
            "vendor_tax_id",
            "date",
            "currency",
            "subtotal",
            "tax",
            "total",
            "payment_method",
            "category",
            "line_items",
            "confidence",
        ],
    },
}

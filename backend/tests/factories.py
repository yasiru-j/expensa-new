import io
import json
from types import SimpleNamespace

from PIL import Image


def make_test_image_bytes(
    size: tuple[int, int] = (20, 20), color: tuple[int, int, int] = (255, 0, 0)
) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG")
    return buffer.getvalue()


def fake_openai_response(content: str) -> SimpleNamespace:
    """Mimics the shape of an OpenAI chat.completions.create() response far
    enough to satisfy `response.choices[0].message.content`."""
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def extraction_payload(**overrides) -> dict:
    payload = {
        "is_receipt": True,
        "vendor": "Corner Cafe",
        "vendor_tax_id": "12 345 678 901",
        "date": "2026-03-14",
        "currency": "AUD",
        "subtotal": 20.00,
        "tax": 2.00,
        "total": 22.00,
        "payment_method": "card",
        "category": "Meals",
        "line_items": [
            {"description": "Coffee", "quantity": 2, "unit_price": 5.00, "amount": 10.00},
            {"description": "Sandwich", "quantity": 1, "unit_price": 10.00, "amount": 10.00},
        ],
        "confidence": 0.95,
    }
    payload.update(overrides)
    return payload


def fake_receipt_response(**overrides) -> SimpleNamespace:
    return fake_openai_response(json.dumps(extraction_payload(**overrides)))

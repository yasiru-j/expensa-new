from decimal import Decimal
from unittest.mock import AsyncMock

from app.core.config import get_settings
from app.extraction.service import extract_with_tiering
from tests.factories import fake_openai_response, fake_receipt_response, make_test_image_bytes

settings = get_settings()
IMAGE_BYTES = make_test_image_bytes()


def _model_used(client: AsyncMock, call_index: int) -> str:
    return client.chat.completions.create.call_args_list[call_index].kwargs["model"]


async def test_high_confidence_clean_extraction_stays_on_the_cheap_model() -> None:
    client = AsyncMock()
    client.chat.completions.create.return_value = fake_receipt_response(confidence=0.95)

    extraction, validated = await extract_with_tiering(client, IMAGE_BYTES, "image/jpeg")

    assert client.chat.completions.create.call_count == 1
    assert _model_used(client, 0) == settings.openai_extraction_model
    assert validated.field_flags == {}


async def test_low_confidence_escalates_to_the_larger_model() -> None:
    client = AsyncMock()
    client.chat.completions.create.side_effect = [
        fake_receipt_response(confidence=0.4, vendor="Cheap Model Read"),
        fake_receipt_response(confidence=0.9, vendor="Escalated Model Read"),
    ]

    extraction, validated = await extract_with_tiering(client, IMAGE_BYTES, "image/jpeg")

    assert client.chat.completions.create.call_count == 2
    assert _model_used(client, 0) == settings.openai_extraction_model
    assert _model_used(client, 1) == settings.openai_extraction_model_escalated
    # The escalated tier's result wins, not the cheap tier's.
    assert extraction.vendor == "Escalated Model Read"
    assert validated.vendor == "Escalated Model Read"


async def test_validation_flag_escalates_even_with_high_confidence() -> None:
    client = AsyncMock()
    client.chat.completions.create.side_effect = [
        # High self-reported confidence, but arithmetic doesn't add up —
        # validate_and_normalize flags it, which must trigger escalation on
        # its own, independent of the model's own confidence.
        fake_receipt_response(confidence=0.95, subtotal=20.00, tax=2.00, total=99.00),
        fake_receipt_response(confidence=0.95, subtotal=20.00, tax=2.00, total=22.00),
    ]

    extraction, validated = await extract_with_tiering(client, IMAGE_BYTES, "image/jpeg")

    assert client.chat.completions.create.call_count == 2
    assert _model_used(client, 1) == settings.openai_extraction_model_escalated
    assert validated.field_flags == {}
    assert validated.total == Decimal("22.00")


async def test_does_not_escalate_twice() -> None:
    client = AsyncMock()
    # Both tiers come back low-confidence — must still stop after one escalation.
    client.chat.completions.create.side_effect = [
        fake_receipt_response(confidence=0.3),
        fake_receipt_response(confidence=0.3),
    ]

    await extract_with_tiering(client, IMAGE_BYTES, "image/jpeg")

    assert client.chat.completions.create.call_count == 2


async def test_escalation_call_itself_failing_falls_back_to_the_cheap_result() -> None:
    client = AsyncMock()
    # The escalated tier's own retry-once also exhausts (2 more calls), both malformed.
    client.chat.completions.create.side_effect = [
        fake_receipt_response(confidence=0.3, vendor="Cheap Model Read"),
        fake_openai_response("not valid json"),
        fake_openai_response("still not valid json"),
    ]

    extraction, validated = await extract_with_tiering(client, IMAGE_BYTES, "image/jpeg")

    assert client.chat.completions.create.call_count == 3
    assert extraction.vendor == "Cheap Model Read"
    assert validated.vendor == "Cheap Model Read"


async def test_quota_relevant_call_count_is_the_same_regardless_of_tiering_path() -> None:
    """Documents the invariant the upload handler relies on: quota increments
    once per upload, wrapping this whole function — regardless of how many
    actual OpenAI calls happen inside it. This test just confirms the call
    count stays bounded and deterministic for a clean vs. an escalated path,
    the two behaviors expenses.py's single increment-before-call is built to
    cover uniformly."""
    clean_client = AsyncMock()
    clean_client.chat.completions.create.return_value = fake_receipt_response(confidence=0.95)
    await extract_with_tiering(clean_client, IMAGE_BYTES, "image/jpeg")
    assert clean_client.chat.completions.create.call_count == 1

    escalated_client = AsyncMock()
    escalated_client.chat.completions.create.side_effect = [
        fake_receipt_response(confidence=0.2),
        fake_receipt_response(confidence=0.9),
    ]
    await extract_with_tiering(escalated_client, IMAGE_BYTES, "image/jpeg")
    assert escalated_client.chat.completions.create.call_count == 2

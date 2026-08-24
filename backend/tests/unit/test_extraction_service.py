from unittest.mock import AsyncMock

import pytest

from app.extraction.exceptions import ExtractionFailedError, NonReceiptError
from app.extraction.service import extract_receipt
from tests.factories import fake_openai_response, fake_receipt_response, make_test_image_bytes

IMAGE_BYTES = make_test_image_bytes()


async def test_extract_receipt_succeeds_on_first_call() -> None:
    client = AsyncMock()
    client.chat.completions.create.return_value = fake_receipt_response(vendor="Corner Cafe")

    result = await extract_receipt(client, IMAGE_BYTES, "image/jpeg")

    assert result.vendor == "Corner Cafe"
    assert client.chat.completions.create.call_count == 1


async def test_extract_receipt_retries_once_on_malformed_json_then_succeeds() -> None:
    client = AsyncMock()
    client.chat.completions.create.side_effect = [
        fake_openai_response("not valid json"),
        fake_receipt_response(vendor="Corner Cafe"),
    ]

    result = await extract_receipt(client, IMAGE_BYTES, "image/jpeg")

    assert result.vendor == "Corner Cafe"
    assert client.chat.completions.create.call_count == 2


async def test_extract_receipt_raises_after_two_malformed_responses() -> None:
    client = AsyncMock()
    client.chat.completions.create.side_effect = [
        fake_openai_response("not valid json"),
        fake_openai_response("still not valid json"),
    ]

    with pytest.raises(ExtractionFailedError):
        await extract_receipt(client, IMAGE_BYTES, "image/jpeg")

    assert client.chat.completions.create.call_count == 2


async def test_extract_receipt_retries_on_transport_error_then_succeeds() -> None:
    client = AsyncMock()
    client.chat.completions.create.side_effect = [
        ConnectionError("boom"),
        fake_receipt_response(vendor="Corner Cafe"),
    ]

    result = await extract_receipt(client, IMAGE_BYTES, "image/jpeg")

    assert result.vendor == "Corner Cafe"
    assert client.chat.completions.create.call_count == 2


async def test_extract_receipt_raises_after_two_transport_errors() -> None:
    client = AsyncMock()
    client.chat.completions.create.side_effect = [
        ConnectionError("boom"),
        TimeoutError("boom again"),
    ]

    with pytest.raises(ExtractionFailedError):
        await extract_receipt(client, IMAGE_BYTES, "image/jpeg")

    assert client.chat.completions.create.call_count == 2


async def test_extract_receipt_raises_non_receipt_error_without_retrying() -> None:
    client = AsyncMock()
    client.chat.completions.create.return_value = fake_receipt_response(is_receipt=False)

    with pytest.raises(NonReceiptError):
        await extract_receipt(client, IMAGE_BYTES, "image/jpeg")

    # Deterministic (temperature=0) call on the same image — retrying wastes an
    # API call and won't produce a different answer.
    assert client.chat.completions.create.call_count == 1

import base64
import time

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.extraction.exceptions import (
    ExtractionFailedError,
    ExtractionParseError,
    ExtractionTransportError,
    NonReceiptError,
)
from app.extraction.prompt import EXTRACTION_PROMPT
from app.extraction.schema import RECEIPT_JSON_SCHEMA, ReceiptExtraction
from app.extraction.validation import ValidatedExpense, validate_and_normalize

settings = get_settings()
logger = get_logger("expensa.extraction")


async def _call_openai(
    client: AsyncOpenAI, image_bytes: bytes, mime_type: str, model: str
) -> ReceiptExtraction:
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    started = time.perf_counter()
    try:
        response = await client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_schema", "json_schema": RECEIPT_JSON_SCHEMA},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": EXTRACTION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                        },
                    ],
                }
            ],
        )
    except Exception as exc:
        log_event(
            logger,
            "extraction_call",
            model=model,
            outcome="transport_error",
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        raise ExtractionTransportError(str(exc)) from exc

    content = response.choices[0].message.content
    duration_ms = round((time.perf_counter() - started) * 1000, 1)
    try:
        parsed = ReceiptExtraction.model_validate_json(content)
    except (ValidationError, ValueError, TypeError) as exc:
        log_event(
            logger, "extraction_call", model=model, outcome="parse_error", duration_ms=duration_ms
        )
        raise ExtractionParseError(str(exc)) from exc

    log_event(
        logger,
        "extraction_call",
        model=model,
        outcome="non_receipt" if not parsed.is_receipt else "success",
        duration_ms=duration_ms,
        confidence=parsed.confidence,
    )
    return parsed


async def extract_receipt(
    client: AsyncOpenAI,
    image_bytes: bytes,
    mime_type: str,
    model: str | None = None,
) -> ReceiptExtraction:
    """Calls the vision model, retrying once more on any parse/transport failure
    (TRD §5.4 — "a parse/validation failure triggers one retry, then a `failed`
    status"). Raises NonReceiptError immediately, without retrying, if the model
    reports the document isn't a receipt — a deterministic (temperature=0) call
    on the same image won't produce a different answer. Raises
    ExtractionFailedError once both attempts fail to produce usable output.

    model defaults to the cheap tier (settings.openai_extraction_model);
    extract_with_tiering is what actually escalates to the larger model.
    """
    resolved_model = model or settings.openai_extraction_model
    last_error: Exception | None = None

    for _attempt in range(2):
        try:
            data = await _call_openai(client, image_bytes, mime_type, resolved_model)
        except (ExtractionParseError, ExtractionTransportError) as exc:
            last_error = exc
            continue

        if not data.is_receipt:
            raise NonReceiptError(
                "The uploaded document does not appear to be a receipt or invoice."
            )

        return data

    raise ExtractionFailedError(f"Extraction failed after retry: {last_error}") from last_error


async def extract_with_tiering(
    client: AsyncOpenAI, image_bytes: bytes, mime_type: str
) -> tuple[ReceiptExtraction, ValidatedExpense]:
    """Cheap model first; escalates to the larger model ONCE if the cheap
    model's own confidence is below the configured threshold OR server-side
    validation flags an issue (TRD §8 cost lever). Each tier still gets
    extract_receipt's own one-retry-on-parse/transport-failure behavior —
    tiering adds at most one more full attempt on top of that, so a single
    upload makes at most 4 OpenAI calls (2 tiers x up to 2 attempts each).

    If escalation itself fails outright (NonReceiptError can't fire here —
    the cheap-tier call above would already have raised it — but
    ExtractionFailedError can), the cheap tier's still-valid result is kept
    rather than discarded.
    """
    extraction = await extract_receipt(
        client, image_bytes, mime_type, model=settings.openai_extraction_model
    )
    validated = validate_and_normalize(extraction)

    needs_escalation = extraction.confidence < settings.model_tier_confidence_threshold or bool(
        validated.field_flags
    )
    log_event(
        logger,
        "extraction_tiering",
        escalating=needs_escalation,
        cheap_tier_confidence=extraction.confidence,
        field_flags_count=len(validated.field_flags),
    )
    if not needs_escalation:
        return extraction, validated

    try:
        escalated_extraction = await extract_receipt(
            client, image_bytes, mime_type, model=settings.openai_extraction_model_escalated
        )
    except ExtractionFailedError:
        return extraction, validated

    escalated_validated = validate_and_normalize(escalated_extraction)
    return escalated_extraction, escalated_validated

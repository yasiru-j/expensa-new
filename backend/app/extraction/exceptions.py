class ExtractionError(Exception):
    """Base for all extraction-pipeline errors."""


class NonReceiptError(ExtractionError):
    """The model reported this document is not a receipt/invoice — never retried,
    since a deterministic (temperature=0) call on the same image won't change that."""


class ExtractionParseError(ExtractionError):
    """The model's response didn't parse into the expected schema."""


class ExtractionTransportError(ExtractionError):
    """The OpenAI call itself failed (network, API error, timeout, etc.)."""


class ExtractionFailedError(ExtractionError):
    """Retries exhausted; extraction could not be completed."""

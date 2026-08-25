"""ARQ worker: processes multi-page PDF extraction jobs off the request
path (TRD §5.5), and runs the periodic stale-processing-row sweep now that a
long-running worker process exists (see app/db/maintenance.py's docstring).

Runs as a SEPARATE process from the FastAPI app — the request-scoped get_db
dependency does not, and cannot, reach it. Each job opens its OWN
expensa_app-role session and sets app.user_id itself via
app.core.deps.user_scoped_session, exactly as the inline (single-page)
upload path does, so Postgres RLS covers this write path too.

Run with: arq app.worker.WorkerSettings
(the `worker` service in docker-compose.yml, gated behind the `worker`
Compose profile — see the README's async-processing section for why it
isn't part of the default `docker compose up`.)
"""

import uuid

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.deps import user_scoped_session
from app.core.logging import configure_logging, get_logger, log_event
from app.db.maintenance import sweep_all_stale_processing_rows
from app.db.worker_session import owner_scoped_session
from app.extraction.client import get_openai_client
from app.extraction.exceptions import ExtractionFailedError, NonReceiptError
from app.extraction.image_prep import downscale_image, render_pdf_first_page
from app.extraction.persistence import persist_extraction_outcome
from app.extraction.service import extract_with_tiering
from app.extraction.validation import ValidatedExpense
from app.storage.s3 import get_object
from app.usage.quota import QuotaExceededError, try_increment_usage

settings = get_settings()
logger = get_logger("expensa.worker")


async def process_multi_page_pdf(
    _ctx: dict, expense_id: str, user_id: str, object_key: str
) -> None:
    """Renders page 1 of the stored PDF, downscales, runs the same tiered
    extraction as the inline path, and persists the outcome — the async
    counterpart to upload_expense's inline flow for single-page files.

    expense_id/user_id/object_key all come from OUR OWN enqueue call in
    upload_expense (never attacker-controlled), but this still goes through
    user_scoped_session — the same RLS-scoped pattern as the inline path —
    rather than trusting the payload's pairing implicitly.
    """
    user_uuid = uuid.UUID(user_id)
    expense_uuid = uuid.UUID(expense_id)
    log_event(logger, "multi_page_job_started", expense_id=expense_id)

    validated: ValidatedExpense | None = None
    try:
        pdf_bytes = await get_object(object_key)
        image_bytes, image_mime = render_pdf_first_page(pdf_bytes)
        downscaled_bytes, downscaled_mime = downscale_image(image_bytes, image_mime)

        # Atomic quota gate, immediately before the paid call — same
        # exactly-once-per-attempt rule as the inline path, just enforced
        # here instead, since this is where the paid call actually happens
        # for a multi-page PDF.
        async with user_scoped_session(user_uuid) as session:
            quota_ok = await try_increment_usage(session, user_uuid)
        if not quota_ok:
            log_event(logger, "quota_blocked", user_id=user_id, stage="worker")
            raise QuotaExceededError("Monthly extraction quota reached before the async job ran.")

        openai_client = get_openai_client()
        _extraction, validated = await extract_with_tiering(
            openai_client, downscaled_bytes, downscaled_mime
        )
    except (NonReceiptError, ExtractionFailedError, QuotaExceededError):
        pass  # row lands at status=failed below
    except Exception:
        logger.exception(
            "multi_page_job_unexpected_error", extra={"fields": {"expense_id": expense_id}}
        )

    async with user_scoped_session(user_uuid) as session:
        result_status = await persist_extraction_outcome(session, expense_uuid, validated)

    log_event(
        logger,
        "multi_page_job_completed",
        expense_id=expense_id,
        status=result_status or "row_missing",
    )


async def sweep_stale_processing_cron(_ctx: dict) -> None:
    async with owner_scoped_session() as session:
        swept = await sweep_all_stale_processing_rows(session)
    if swept:
        log_event(logger, "periodic_sweep", flipped_to_failed=swept)


async def _on_startup(_ctx: dict) -> None:
    configure_logging()


class WorkerSettings:
    functions = [process_multi_page_pdf]
    cron_jobs = [cron(sweep_stale_processing_cron, minute=set(range(0, 60, 5)))]
    on_startup = _on_startup
    redis_settings = RedisSettings.from_dsn(settings.redis_url)

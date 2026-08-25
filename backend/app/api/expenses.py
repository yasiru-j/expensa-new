import hashlib
import uuid
from datetime import date as date_type

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, status
from openai import AsyncOpenAI
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.expense_filters import (
    CATEGORY_PATTERN,
    SORT_OPTIONS,
    STATUS_PATTERN,
    build_expense_conditions,
)
from app.core.arq import get_arq_pool
from app.core.config import get_settings
from app.core.deps import get_current_user, get_current_user_id, get_db, user_scoped_session
from app.core.logging import get_logger, log_event
from app.db.maintenance import sweep_stale_processing_rows
from app.db.models.expense import Expense
from app.db.models.line_item import LineItem
from app.db.models.user import User
from app.extraction.client import get_openai_client
from app.extraction.duplicates import duplicate_flag_expression, is_potential_duplicate
from app.extraction.exceptions import ExtractionFailedError, NonReceiptError
from app.extraction.image_prep import (
    UnsupportedFileTypeError,
    downscale_image,
    get_pdf_page_count,
    render_pdf_first_page,
    sniff_content_type,
)
from app.extraction.persistence import persist_extraction_outcome
from app.extraction.provenance import apply_user_edits
from app.extraction.service import extract_with_tiering
from app.schemas.expense import (
    ExpenseListItem,
    ExpensePatchRequest,
    ExpenseRead,
    ExpenseUploadResponse,
    LineItemRead,
    PaginatedExpenses,
)
from app.storage.s3 import delete_object, object_key_for, presigned_get_url, put_object
from app.usage.quota import QuotaExceededError, get_current_usage, try_increment_usage
from app.usage.rate_limit import check_rate_limit

router = APIRouter(prefix="/api/expenses", tags=["expenses"])
settings = get_settings()
logger = get_logger("expensa.upload")

EXTENSION_FOR = {"image/jpeg": "jpg", "image/png": "png", "application/pdf": "pdf"}
CHUNK_SIZE = 1024 * 1024  # 1 MiB
IDEMPOTENCY_INDEX = ["user_id", "file_hash"]
IDEMPOTENCY_INDEX_WHERE = text("status <> 'failed'")


async def _rate_limited_user_id(
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> uuid.UUID:
    """auth -> rate limit, in that order: this dependency chains off
    get_current_user_id, so authentication always resolves first, and a
    rate-limited caller is rejected before any handler body code (including
    the quota check) runs."""
    allowed, retry_after = await check_rate_limit(
        user_id, "upload", settings.upload_rate_limit_per_hour, settings.rate_limit_window_seconds
    )
    if not allowed:
        log_event(logger, "rate_limit_blocked", user_id=str(user_id), retry_after=retry_after)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many uploads. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )
    return user_id


async def _read_upload_with_limit(file: UploadFile, max_bytes: int) -> bytes:
    """Reads in chunks, aborting as soon as the cap is exceeded — never
    buffers the full body of an oversized file."""
    declared_size = file.size
    if declared_size is not None and declared_size > max_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"File exceeds the {max_bytes // (1024 * 1024)}MB upload limit.",
        )

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"File exceeds the {max_bytes // (1024 * 1024)}MB upload limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def _to_expense_read(db: AsyncSession, expense: Expense) -> ExpenseRead:
    line_items = (
        (await db.execute(select(LineItem).where(LineItem.expense_id == expense.id)))
        .scalars()
        .all()
    )
    file_url = await presigned_get_url(expense.file_url) if expense.file_url else None

    base = ExpenseListItem.model_validate(expense)
    base.is_potential_duplicate = await is_potential_duplicate(db, expense)
    return ExpenseRead(
        **base.model_dump(),
        vendor_tax_id=expense.vendor_tax_id,
        subtotal=expense.subtotal,
        tax=expense.tax,
        payment_method=expense.payment_method,
        updated_at=expense.updated_at,
        line_items=[LineItemRead.model_validate(li) for li in line_items],
        file_url=file_url,
        field_provenance=expense.field_provenance,
    )


@router.post("/upload", response_model=ExpenseUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_expense(
    file: UploadFile,
    user_id: uuid.UUID = Depends(_rate_limited_user_id),
    openai_client: AsyncOpenAI = Depends(get_openai_client),
) -> ExpenseUploadResponse:
    # Guardrail order (TRD §6/§8): auth -> rate limit (both above, via the
    # dependency chain) -> quota -> file validation -> extract.
    #
    # This early quota check is a cheap, read-only fast-fail — no point
    # reading/parsing a file for a user already over quota — but it is NOT
    # the authoritative gate (see try_increment_usage below, and the async
    # worker's own gate for multi-page PDFs, for that).
    log_event(logger, "upload_received", user_id=str(user_id))
    async with user_scoped_session(user_id) as session:
        current_usage = await get_current_usage(session, user_id)
    if current_usage >= settings.monthly_extraction_quota:
        log_event(logger, "quota_blocked", user_id=str(user_id), stage="early")
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Monthly extraction quota reached ({settings.monthly_extraction_quota}/month). "
                "Try again next month."
            ),
        )

    raw_bytes = await _read_upload_with_limit(file, settings.max_upload_size_bytes)
    if not raw_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file.")

    try:
        content_type = sniff_content_type(raw_bytes)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    # Single-page images and single-page PDFs are processed inline, below,
    # same as ever. A multi-page PDF (2..max_pdf_pages) is instead dispatched
    # to the async worker (TRD §5.5) — render/downscale/extract all move off
    # the request path, and the response comes back with status="processing"
    # immediately rather than waiting.
    is_multi_page_pdf = False
    page_count = 1
    if content_type == "application/pdf":
        page_count = get_pdf_page_count(raw_bytes)
        if page_count > settings.max_pdf_pages:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"PDF exceeds the {settings.max_pdf_pages}-page limit.",
            )
        if page_count > 1:
            is_multi_page_pdf = True
        else:
            image_bytes, image_mime = render_pdf_first_page(raw_bytes)
    else:
        image_bytes, image_mime = raw_bytes, content_type

    file_hash = hashlib.sha256(raw_bytes).hexdigest()
    object_key = object_key_for(user_id, EXTENSION_FOR[content_type])

    # --- txn 1: sweep any stale row for this user, then idempotency-safe insert ---
    async with user_scoped_session(user_id) as session:
        # A row stuck at `processing` (a crash between txn 1 and txn 2 on a
        # PREVIOUS upload) would otherwise permanently block a fresh retry of
        # that same file below — the unique index treats `processing` as a
        # live, conflicting status.
        await sweep_stale_processing_rows(session)

        # ON CONFLICT DO NOTHING against the partial unique index, rather
        # than a SELECT-then-INSERT: the database resolves the race between
        # two concurrent identical uploads atomically. Whichever request's
        # INSERT loses returns no row and falls back to reading the winner's.
        insert_stmt = (
            pg_insert(Expense)
            .values(user_id=user_id, file_url=object_key, file_hash=file_hash, status="processing")
            .on_conflict_do_nothing(
                index_elements=IDEMPOTENCY_INDEX, index_where=IDEMPOTENCY_INDEX_WHERE
            )
            .returning(Expense.id)
        )
        inserted = (await session.execute(insert_stmt)).first()

        if inserted is None:
            existing = await session.scalar(
                select(Expense).where(Expense.file_hash == file_hash, Expense.status != "failed")
            )
            log_event(
                logger, "upload_idempotent_hit", expense_id=str(existing.id), status=existing.status
            )
            return ExpenseUploadResponse(id=existing.id, status=existing.status)

        expense_id = inserted[0]
    # txn 1 committed; connection released here — nothing DB-related is held
    # open across the OpenAI/MinIO/enqueue calls below.

    if is_multi_page_pdf:
        # The raw PDF is stored now so the worker can fetch it back by key;
        # everything else (render, downscale, quota gate, extract, persist)
        # happens inside the job, off this request entirely.
        await put_object(object_key, raw_bytes, content_type)
        pool = await get_arq_pool()
        await pool.enqueue_job("process_multi_page_pdf", str(expense_id), str(user_id), object_key)
        log_event(
            logger,
            "upload_dispatched_async",
            expense_id=str(expense_id),
            user_id=str(user_id),
            page_count=page_count,
        )
        return ExpenseUploadResponse(id=expense_id, status="processing")

    validated = None
    try:
        await put_object(object_key, raw_bytes, content_type)
        downscaled_bytes, downscaled_mime = downscale_image(image_bytes, image_mime)

        # --- atomic quota gate, immediately before the paid call ---
        # A single increment covers the WHOLE extraction attempt below, no
        # matter how many actual OpenAI calls it makes internally (up to 2
        # tiers x up to 2 attempts each) — quota counts uploads, not raw API
        # calls.
        async with user_scoped_session(user_id) as session:
            quota_ok = await try_increment_usage(session, user_id)
        if not quota_ok:
            log_event(logger, "quota_blocked", user_id=str(user_id), stage="atomic")
            raise QuotaExceededError("Monthly extraction quota reached mid-request.")

        _extraction, validated = await extract_with_tiering(
            openai_client, downscaled_bytes, downscaled_mime
        )
    except (NonReceiptError, ExtractionFailedError, QuotaExceededError):
        pass  # row lands at status=failed below
    except Exception:
        # Any unexpected failure (storage, downscaling, a transport error type
        # not already covered) must still land the row at `failed` — never
        # leave it stuck at `processing`.
        pass

    # --- txn 2: persist the outcome ---
    async with user_scoped_session(user_id) as session:
        result_status = await persist_extraction_outcome(session, expense_id, validated)
        log_event(logger, "upload_completed", expense_id=str(expense_id), status=result_status)
        return ExpenseUploadResponse(id=expense_id, status=result_status)


@router.get("", response_model=PaginatedExpenses)
async def list_expenses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("date_desc", pattern="^(date_desc|date_asc|created_desc|created_asc)$"),
    status_filter: str | None = Query(None, alias="status", pattern=STATUS_PATTERN),
    date_from: date_type | None = Query(None),
    date_to: date_type | None = Query(None),
    category: str | None = Query(None, pattern=CATEGORY_PATTERN),
    q: str | None = Query(
        None,
        min_length=1,
        max_length=200,
        description="Case-insensitive, partial-match vendor search",
    ),
) -> PaginatedExpenses:
    # No explicit WHERE user_id filter anywhere in this router: isolation is
    # enforced entirely by Postgres RLS, per the app's whole security model.
    #
    # status is unfiltered by default so the review workflow can see
    # pending/processing/ready/failed rows, not just confirmed ones. Phase 4's
    # dashboard aggregation is expected to pass status=confirmed explicitly —
    # "only confirmed rows count as final" is a query-time choice, not a
    # change to what this endpoint returns by default.
    await sweep_stale_processing_rows(db)

    conditions = build_expense_conditions(
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        category=category,
        q=q,
    )

    count_query = select(func.count()).select_from(Expense)
    items_query = select(
        Expense, duplicate_flag_expression().label("is_potential_duplicate")
    ).order_by(SORT_OPTIONS[sort])
    for condition in conditions:
        count_query = count_query.where(condition)
        items_query = items_query.where(condition)

    total = await db.scalar(count_query)
    result = await db.execute(items_query.offset((page - 1) * page_size).limit(page_size))
    rows = result.all()

    items = []
    for expense, is_dup in rows:
        item = ExpenseListItem.model_validate(expense)
        item.is_potential_duplicate = is_dup
        items.append(item)

    return PaginatedExpenses(
        items=items,
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/{expense_id}", response_model=ExpenseRead)
async def get_expense(
    expense_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExpenseRead:
    expense = await db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")

    return await _to_expense_read(db, expense)


@router.patch("/{expense_id}", response_model=ExpenseRead)
async def update_expense(
    expense_id: uuid.UUID,
    body: ExpensePatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExpenseRead:
    expense = await db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")

    if expense.status != "ready":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Only a 'ready' expense can be edited (this one is '{expense.status}').",
        )

    changed_fields = body.model_fields_set
    for field_name, value in body.model_dump(exclude_unset=True).items():
        setattr(expense, field_name, value)

    if changed_fields:
        expense.field_provenance = apply_user_edits(expense.field_provenance, changed_fields)

    await db.flush()
    # updated_at has an onupdate=func.now() server-side default, so the flush
    # expires it — refresh() reloads it the async-safe way. A bare attribute
    # access here would try a synchronous lazy-load outside the SQLAlchemy
    # async greenlet context and raise MissingGreenlet.
    await db.refresh(expense)
    return await _to_expense_read(db, expense)


@router.post("/{expense_id}/confirm", response_model=ExpenseRead)
async def confirm_expense(
    expense_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExpenseRead:
    expense = await db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")

    if expense.status != "ready":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Only a 'ready' expense can be confirmed (this one is '{expense.status}').",
        )

    expense.status = "confirmed"
    await db.flush()
    await db.refresh(expense)
    return await _to_expense_read(db, expense)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    expense = await db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")

    object_key = expense.file_url
    await db.delete(expense)

    if object_key:
        # Deferred until after the response is sent (i.e. after this
        # transaction has actually committed), so a later failure in this
        # request can't leave the S3 object deleted but the row rolled back.
        background_tasks.add_task(delete_object, object_key)

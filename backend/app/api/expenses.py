import hashlib
import uuid
from datetime import date as date_type

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, status
from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user, get_current_user_id, get_db, user_scoped_session
from app.db.models.expense import STATUSES, Expense
from app.db.models.line_item import LineItem
from app.db.models.user import User
from app.extraction.client import get_openai_client
from app.extraction.exceptions import ExtractionFailedError, NonReceiptError
from app.extraction.image_prep import (
    UnsupportedFileTypeError,
    downscale_image,
    get_pdf_page_count,
    render_pdf_first_page,
    sniff_content_type,
)
from app.extraction.provenance import apply_user_edits, build_initial_provenance
from app.extraction.schema import CATEGORIES
from app.extraction.service import extract_receipt
from app.extraction.validation import validate_and_normalize
from app.schemas.expense import (
    ExpenseListItem,
    ExpensePatchRequest,
    ExpenseRead,
    ExpenseUploadResponse,
    LineItemRead,
    PaginatedExpenses,
)
from app.storage.s3 import delete_object, object_key_for, presigned_get_url, put_object

router = APIRouter(prefix="/api/expenses", tags=["expenses"])
settings = get_settings()

EXTENSION_FOR = {"image/jpeg": "jpg", "image/png": "png", "application/pdf": "pdf"}
CHUNK_SIZE = 1024 * 1024  # 1 MiB
STATUS_PATTERN = f"^({'|'.join(STATUSES)})$"
CATEGORY_PATTERN = f"^({'|'.join(CATEGORIES)})$"

SORT_OPTIONS = {
    "date_desc": Expense.expense_date.desc().nulls_last(),
    "date_asc": Expense.expense_date.asc().nulls_last(),
    "created_desc": Expense.created_at.desc(),
    "created_asc": Expense.created_at.asc(),
}


def _escape_like(value: str) -> str:
    """Escapes LIKE/ILIKE wildcard characters in free-text user input, so a
    vendor search for e.g. "50% off" doesn't have the % treated as a
    wildcard."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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
    user_id: uuid.UUID = Depends(get_current_user_id),
    openai_client: AsyncOpenAI = Depends(get_openai_client),
) -> ExpenseUploadResponse:
    raw_bytes = await _read_upload_with_limit(file, settings.max_upload_size_bytes)
    if not raw_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file.")

    try:
        content_type = sniff_content_type(raw_bytes)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    if content_type == "application/pdf":
        if get_pdf_page_count(raw_bytes) > settings.max_pdf_pages:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Multi-page PDFs aren't supported yet — please upload a single-page document.",
            )
        image_bytes, image_mime = render_pdf_first_page(raw_bytes)
    else:
        image_bytes, image_mime = raw_bytes, content_type

    file_hash = hashlib.sha256(raw_bytes).hexdigest()

    # --- txn 1: idempotency check + create the processing row ---
    async with user_scoped_session(user_id) as session:
        existing = await session.scalar(select(Expense).where(Expense.file_hash == file_hash))
        if existing is not None:
            return ExpenseUploadResponse(id=existing.id, status=existing.status)

        object_key = object_key_for(user_id, EXTENSION_FOR[content_type])
        expense = Expense(
            user_id=user_id, file_url=object_key, file_hash=file_hash, status="processing"
        )
        session.add(expense)
        await session.flush()
        expense_id = expense.id
    # txn 1 committed; connection released here — nothing DB-related is held
    # open across the OpenAI/MinIO calls below.

    validated = None
    try:
        await put_object(object_key, raw_bytes, content_type)
        downscaled_bytes, downscaled_mime = downscale_image(image_bytes, image_mime)
        extraction = await extract_receipt(openai_client, downscaled_bytes, downscaled_mime)
        validated = validate_and_normalize(extraction)
    except (NonReceiptError, ExtractionFailedError):
        pass  # row lands at status=failed below
    except Exception:
        # Any unexpected failure (storage, downscaling, a transport error type
        # not already covered) must still land the row at `failed` — never
        # leave it stuck at `processing`.
        pass

    # --- txn 2: persist the outcome ---
    async with user_scoped_session(user_id) as session:
        expense = await session.get(Expense, expense_id)
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
        return ExpenseUploadResponse(id=expense.id, status=expense.status)


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
    conditions = []
    if status_filter is not None:
        conditions.append(Expense.status == status_filter)
    if date_from is not None:
        conditions.append(Expense.expense_date >= date_from)
    if date_to is not None:
        conditions.append(Expense.expense_date <= date_to)
    if category is not None:
        conditions.append(Expense.category == category)
    if q:
        conditions.append(Expense.vendor.ilike(f"%{_escape_like(q)}%", escape="\\"))

    count_query = select(func.count()).select_from(Expense)
    items_query = select(Expense).order_by(SORT_OPTIONS[sort])
    for condition in conditions:
        count_query = count_query.where(condition)
        items_query = items_query.where(condition)

    total = await db.scalar(count_query)
    result = await db.execute(items_query.offset((page - 1) * page_size).limit(page_size))
    items = result.scalars().all()

    return PaginatedExpenses(
        items=[ExpenseListItem.model_validate(item) for item in items],
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

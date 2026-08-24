import hashlib
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.maintenance import sweep_stale_processing_rows
from app.db.models.expense import Expense
from app.db.models.user import User
from tests.factories import fake_receipt_response, make_test_image_bytes


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_sweep_flips_an_aged_processing_row_to_failed(
    owner_session: AsyncSession, app_session_as
) -> None:
    user = User(email="reaper-direct@example.com", password_hash="not-a-real-hash")
    owner_session.add(user)
    await owner_session.flush()

    old_expense = Expense(
        user_id=user.id,
        vendor="Stuck Upload",
        status="processing",
        created_at=datetime.now(UTC) - timedelta(minutes=999),
    )
    owner_session.add(old_expense)
    await owner_session.commit()

    async with app_session_as(user.id) as session:
        swept = await sweep_stale_processing_rows(session)

    assert swept == 1

    # owner_session's sessionmaker uses expire_on_commit=False, so the ALREADY
    # in-identity-map old_expense would otherwise return its stale in-memory
    # status rather than reflecting the sweep, which ran through a different
    # session/connection. refresh() forces a real read.
    await owner_session.refresh(old_expense)
    assert old_expense.status == "failed"


async def test_sweep_leaves_a_recent_processing_row_alone(
    owner_session: AsyncSession, app_session_as
) -> None:
    user = User(email="reaper-recent@example.com", password_hash="not-a-real-hash")
    owner_session.add(user)
    await owner_session.flush()

    recent_expense = Expense(user_id=user.id, vendor="Just Started", status="processing")
    owner_session.add(recent_expense)
    await owner_session.commit()

    async with app_session_as(user.id) as session:
        swept = await sweep_stale_processing_rows(session)

    assert swept == 0

    await owner_session.refresh(recent_expense)
    assert recent_expense.status == "processing"


async def test_sweep_leaves_other_statuses_alone(
    owner_session: AsyncSession, app_session_as
) -> None:
    user = User(email="reaper-other-statuses@example.com", password_hash="not-a-real-hash")
    owner_session.add(user)
    await owner_session.flush()

    ready = Expense(
        user_id=user.id,
        vendor="Already Done",
        status="ready",
        created_at=datetime.now(UTC) - timedelta(minutes=999),
    )
    owner_session.add(ready)
    await owner_session.commit()

    async with app_session_as(user.id) as session:
        swept = await sweep_stale_processing_rows(session)

    assert swept == 0
    await owner_session.refresh(ready)
    assert ready.status == "ready"


async def test_listing_expenses_sweeps_a_stale_row_for_that_user(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("reaper-via-list@example.com")
    me = await client.get("/api/auth/me", headers=_auth_headers(token))
    user_id = me.json()["id"]

    stuck = Expense(
        user_id=user_id,
        vendor="Stuck Upload",
        status="processing",
        created_at=datetime.now(UTC) - timedelta(minutes=999),
    )
    owner_session.add(stuck)
    await owner_session.commit()

    listing = await client.get("/api/expenses", headers=_auth_headers(token))

    assert listing.status_code == 200
    item = next(i for i in listing.json()["items"] if i["id"] == str(stuck.id))
    assert item["status"] == "failed"


async def test_stale_processing_row_does_not_block_a_fresh_reupload(
    client: AsyncClient, signup_user, owner_session: AsyncSession, mock_openai_client
) -> None:
    """A row stuck at `processing` (e.g. a crash between the two upload
    transactions) must not permanently block a retry of the same file — the
    upload path sweeps before checking the idempotency index."""
    token = await signup_user("reaper-unblocks-reupload@example.com")
    me = await client.get("/api/auth/me", headers=_auth_headers(token))
    user_id = me.json()["id"]

    image = make_test_image_bytes()
    file_hash = hashlib.sha256(image).hexdigest()

    stuck = Expense(
        user_id=user_id,
        vendor=None,
        status="processing",
        file_hash=file_hash,
        created_at=datetime.now(UTC) - timedelta(minutes=999),
    )
    owner_session.add(stuck)
    await owner_session.commit()

    mock_openai_client.chat.completions.create.return_value = fake_receipt_response()
    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", image, "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert resp.status_code == 201
    assert resp.json()["status"] == "ready"
    assert resp.json()["id"] != str(stuck.id)  # a genuinely new attempt, not the stuck row

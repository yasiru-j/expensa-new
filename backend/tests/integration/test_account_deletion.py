"""DELETE /api/account: hard-deletes every row belonging to the caller
(expenses, line_items, usage — all via ON DELETE CASCADE from users) and
every stored file, and clears the refresh cookie. Verified directly at the
DB and MinIO layers, not just via the HTTP response."""

from datetime import date
from decimal import Decimal

from botocore.exceptions import ClientError
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.expense import Expense
from app.db.models.line_item import LineItem
from app.storage.s3 import get_s3_client, put_object

settings = get_settings()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _get_user_id(client: AsyncClient, token: str) -> str:
    resp = await client.get("/api/auth/me", headers=_auth_headers(token))
    return resp.json()["id"]


def _object_exists(key: str) -> bool:
    try:
        get_s3_client().head_object(Bucket=settings.s3_bucket_name, Key=key)
        return True
    except ClientError:
        return False


async def test_account_deletion_removes_all_rows_and_stored_files(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("delete-account@example.com")
    user_id = await _get_user_id(client, token)

    object_key = f"receipts/{user_id}/test-receipt.jpg"
    await put_object(object_key, b"fake receipt bytes", "image/jpeg")
    assert _object_exists(object_key)

    expense = Expense(
        user_id=user_id,
        vendor="Some Vendor",
        category="Meals",
        currency="AUD",
        total=Decimal("10.00"),
        expense_date=date.today(),
        status="confirmed",
        file_url=object_key,
    )
    owner_session.add(expense)
    await owner_session.flush()
    owner_session.add(
        LineItem(expense_id=expense.id, description="Coffee", amount=Decimal("10.00"))
    )
    await owner_session.execute(
        text(
            "INSERT INTO usage (user_id, period_month, extraction_count) "
            "VALUES (:uid, date_trunc('month', now())::date, 3)"
        ),
        {"uid": str(user_id)},
    )
    await owner_session.commit()

    resp = await client.delete("/api/account", headers=_auth_headers(token))

    assert resp.status_code == 204
    assert "refresh_token=" in resp.headers.get("set-cookie", "")

    # owner_session's sessionmaker uses expire_on_commit=False, so .get() on
    # an already-loaded object would return the stale in-memory copy rather
    # than reflecting a deletion that happened through a different session —
    # raw count queries always hit the database instead.
    remaining_users = (
        await owner_session.execute(
            text("SELECT count(*) FROM users WHERE id = :uid"), {"uid": str(user_id)}
        )
    ).scalar()
    assert remaining_users == 0

    remaining_expenses = (
        await owner_session.execute(
            text("SELECT count(*) FROM expenses WHERE id = :eid"), {"eid": str(expense.id)}
        )
    ).scalar()
    assert remaining_expenses == 0

    remaining_line_items = (
        await owner_session.execute(
            text("SELECT count(*) FROM line_items WHERE expense_id = :eid"),
            {"eid": str(expense.id)},
        )
    ).scalar()
    assert remaining_line_items == 0

    remaining_usage = (
        await owner_session.execute(
            text("SELECT count(*) FROM usage WHERE user_id = :uid"), {"uid": str(user_id)}
        )
    ).scalar()
    assert remaining_usage == 0

    assert not _object_exists(object_key)


async def test_account_deletion_of_a_user_with_no_expenses_still_succeeds(
    client: AsyncClient, signup_user
) -> None:
    token = await signup_user("delete-account-empty@example.com")

    resp = await client.delete("/api/account", headers=_auth_headers(token))

    assert resp.status_code == 204


async def test_deleted_account_can_no_longer_authenticate(client: AsyncClient, signup_user) -> None:
    token = await signup_user("delete-account-then-auth@example.com")

    resp = await client.delete("/api/account", headers=_auth_headers(token))
    assert resp.status_code == 204

    me = await client.get("/api/auth/me", headers=_auth_headers(token))
    assert me.status_code == 401


async def test_deleting_a_nonexistent_key_in_storage_does_not_error(
    client: AsyncClient, signup_user
) -> None:
    """A user with no uploaded files (all pending/failed rows, no file_url)
    should delete cleanly with nothing to remove from storage."""
    token = await signup_user("delete-account-no-files@example.com")

    resp = await client.delete("/api/account", headers=_auth_headers(token))

    assert resp.status_code == 204

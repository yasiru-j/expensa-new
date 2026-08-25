"""HTTP-level cross-tenant isolation for DELETE /api/account — deleting my
own account must never touch another user's rows or files."""

from datetime import date
from decimal import Decimal

from botocore.exceptions import ClientError
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.expense import Expense
from app.db.models.user import User
from app.storage.s3 import get_s3_client, put_object

settings = get_settings()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _object_exists(key: str) -> bool:
    try:
        get_s3_client().head_object(Bucket=settings.s3_bucket_name, Key=key)
        return True
    except ClientError:
        return False


async def test_deleting_my_account_never_touches_another_users_rows_or_files(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    victim = User(email="victim-account-delete@example.com", password_hash="not-a-real-hash")
    owner_session.add(victim)
    await owner_session.flush()

    victim_key = f"receipts/{victim.id}/victim-file.jpg"
    await put_object(victim_key, b"victim's receipt bytes", "image/jpeg")

    owner_session.add(
        Expense(
            user_id=victim.id,
            vendor="Victim's Vendor",
            category="Software",
            currency="AUD",
            total=Decimal("777.00"),
            expense_date=date.today(),
            status="confirmed",
            file_url=victim_key,
        )
    )
    await owner_session.commit()

    token_a = await signup_user("attacker-account-delete@example.com")

    resp = await client.delete("/api/account", headers=_auth_headers(token_a))
    assert resp.status_code == 204

    # The victim's user row, expense, and stored file must all still exist.
    still_there_user = await owner_session.get(User, victim.id)
    assert still_there_user is not None

    still_there_expense = await owner_session.scalar(
        select(Expense).where(Expense.user_id == victim.id)
    )
    assert still_there_expense is not None

    assert _object_exists(victim_key)

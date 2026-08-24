"""
HTTP-level cross-tenant isolation for GET /api/dashboard/summary — proves the
aggregation query itself is scoped by RLS, not just individual expense reads.
"""

from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.expense import Expense
from app.db.models.user import User


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_dashboard_summary_never_includes_another_users_confirmed_expenses(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    victim = User(email="victim-dashboard@example.com", password_hash="not-a-real-hash")
    owner_session.add(victim)
    await owner_session.flush()

    owner_session.add(
        Expense(
            user_id=victim.id,
            vendor="Victim's Vendor",
            category="Software",
            currency="AUD",
            total=Decimal("777.00"),
            expense_date=date.today(),
            status="confirmed",
        )
    )
    await owner_session.commit()

    token_a = await signup_user("attacker-dashboard@example.com")

    resp = await client.get("/api/dashboard/summary", headers=_auth_headers(token_a))

    assert resp.status_code == 200
    body = resp.json()
    assert body["receipt_count"] == 0
    assert body["month_to_date"] == []
    assert body["by_category"] == []
    assert body["by_month"] == []

"""
HTTP-level cross-tenant isolation for the expenses API — proves RLS holds
THROUGH the app layer (JWT auth + RLS together), not just at the raw-DB level
already covered by tests/security/test_rls_isolation.py.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.expense import Expense
from app.db.models.user import User


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_expense(owner_session: AsyncSession, email: str, **overrides) -> tuple[str, str]:
    """Creates a user and one ready expense directly at the DB layer (as the
    owner role), bypassing the upload/extraction path entirely. Returns
    (user_id, expense_id) as strings."""
    user = User(email=email, password_hash="not-a-real-hash")
    owner_session.add(user)
    await owner_session.flush()

    expense = Expense(
        user_id=user.id,
        vendor=overrides.get("vendor", "Someone Else's Vendor"),
        status=overrides.get("status", "ready"),
        total=overrides.get("total"),
    )
    owner_session.add(expense)
    await owner_session.flush()
    await owner_session.commit()

    return str(user.id), str(expense.id)


async def test_user_cannot_get_another_users_expense(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    _user_b_id, expense_id = await _seed_expense(owner_session, "victim-get@example.com")
    token_a = await signup_user("attacker-get@example.com")

    resp = await client.get(f"/api/expenses/{expense_id}", headers=_auth_headers(token_a))

    assert resp.status_code == 404


async def test_user_cannot_delete_another_users_expense(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    _user_b_id, expense_id = await _seed_expense(owner_session, "victim-delete@example.com")
    token_a = await signup_user("attacker-delete@example.com")

    resp = await client.delete(f"/api/expenses/{expense_id}", headers=_auth_headers(token_a))
    assert resp.status_code == 404

    # Confirm it's untouched, reading back through the owner role.
    still_there = await owner_session.get(Expense, expense_id)
    assert still_there is not None


async def test_user_cannot_see_another_users_expense_in_their_list(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    _user_b_id, expense_id = await _seed_expense(owner_session, "victim-list@example.com")
    token_a = await signup_user("attacker-list@example.com")

    resp = await client.get("/api/expenses", headers=_auth_headers(token_a))

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert all(item["id"] != expense_id for item in body["items"])


async def test_user_cannot_patch_another_users_expense(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    _user_b_id, expense_id = await _seed_expense(owner_session, "victim-patch@example.com")
    token_a = await signup_user("attacker-patch@example.com")

    resp = await client.patch(
        f"/api/expenses/{expense_id}",
        json={"vendor": "Hijacked"},
        headers=_auth_headers(token_a),
    )

    assert resp.status_code == 404

    untouched = await owner_session.get(Expense, expense_id)
    assert untouched.vendor == "Someone Else's Vendor"


async def test_user_cannot_confirm_another_users_expense(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    _user_b_id, expense_id = await _seed_expense(owner_session, "victim-confirm@example.com")
    token_a = await signup_user("attacker-confirm@example.com")

    resp = await client.post(f"/api/expenses/{expense_id}/confirm", headers=_auth_headers(token_a))

    assert resp.status_code == 404

    untouched = await owner_session.get(Expense, expense_id)
    assert untouched.status == "ready"


async def test_user_cannot_find_another_users_expense_via_search(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    _user_b_id, _expense_id = await _seed_expense(
        owner_session, "victim-search@example.com", vendor="Corner Cafe"
    )
    token_a = await signup_user("attacker-search@example.com")

    resp = await client.get("/api/expenses", params={"q": "corner"}, headers=_auth_headers(token_a))

    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_owner_can_still_reach_their_own_expense(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    """Sanity check: isolation isn't just blocking everyone."""
    token_a = await signup_user("owner-sanity@example.com")

    me = await client.get("/api/auth/me", headers=_auth_headers(token_a))
    user_id = me.json()["id"]

    expense = Expense(user_id=user_id, vendor="My Own Vendor", status="ready")
    owner_session.add(expense)
    await owner_session.flush()
    await owner_session.commit()

    resp = await client.get(f"/api/expenses/{expense.id}", headers=_auth_headers(token_a))

    assert resp.status_code == 200
    assert resp.json()["vendor"] == "My Own Vendor"

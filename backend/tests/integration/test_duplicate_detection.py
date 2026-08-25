"""Duplicate-receipt detection: same vendor + expense_date + total flags a
warning on the list row and the detail/review view — never a hard block.
"""

from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.expense import Expense


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _get_user_id(client: AsyncClient, token: str) -> str:
    resp = await client.get("/api/auth/me", headers=_auth_headers(token))
    return resp.json()["id"]


def _seed(owner_session: AsyncSession, user_id: str, **overrides) -> Expense:
    defaults = dict(
        vendor="Corner Cafe",
        category="Meals",
        currency="AUD",
        total=Decimal("12.50"),
        expense_date=date(2026, 1, 15),
        status="ready",
    )
    defaults.update(overrides)
    expense = Expense(user_id=user_id, **defaults)
    owner_session.add(expense)
    return expense


async def test_list_flags_two_rows_sharing_vendor_date_and_total(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("dup-list@example.com")
    user_id = await _get_user_id(client, token)

    _seed(owner_session, user_id)
    _seed(owner_session, user_id)
    await owner_session.commit()

    resp = await client.get("/api/expenses", headers=_auth_headers(token))
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    assert all(item["is_potential_duplicate"] for item in items)


async def test_list_does_not_flag_a_row_with_no_match(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("dup-nomatch@example.com")
    user_id = await _get_user_id(client, token)

    _seed(owner_session, user_id, vendor="Corner Cafe")
    _seed(owner_session, user_id, vendor="Different Vendor")
    await owner_session.commit()

    resp = await client.get("/api/expenses", headers=_auth_headers(token))
    items = resp.json()["items"]
    assert all(not item["is_potential_duplicate"] for item in items)


async def test_a_differing_field_breaks_the_match(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("dup-differs@example.com")
    user_id = await _get_user_id(client, token)

    _seed(owner_session, user_id, total=Decimal("12.50"))
    _seed(owner_session, user_id, total=Decimal("99.99"))  # same vendor+date, different amount
    await owner_session.commit()

    resp = await client.get("/api/expenses", headers=_auth_headers(token))
    items = resp.json()["items"]
    assert all(not item["is_potential_duplicate"] for item in items)


async def test_rows_missing_a_comparable_field_are_never_flagged(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    """Two never-extracted (pending) rows both have NULL vendor/date/total —
    they must never be flagged as duplicates of each other just because they
    share the same NULLs."""
    token = await signup_user("dup-nulls@example.com")
    user_id = await _get_user_id(client, token)

    _seed(owner_session, user_id, vendor=None, expense_date=None, total=None, status="pending")
    _seed(owner_session, user_id, vendor=None, expense_date=None, total=None, status="pending")
    await owner_session.commit()

    resp = await client.get("/api/expenses", headers=_auth_headers(token))
    items = resp.json()["items"]
    assert all(not item["is_potential_duplicate"] for item in items)


async def test_three_way_match_flags_all_three(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("dup-threeway@example.com")
    user_id = await _get_user_id(client, token)

    for _ in range(3):
        _seed(owner_session, user_id)
    await owner_session.commit()

    resp = await client.get("/api/expenses", headers=_auth_headers(token))
    items = resp.json()["items"]
    assert len(items) == 3
    assert all(item["is_potential_duplicate"] for item in items)


async def test_detail_view_surfaces_the_same_flag(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("dup-detail@example.com")
    user_id = await _get_user_id(client, token)

    first = _seed(owner_session, user_id)
    _seed(owner_session, user_id)
    await owner_session.commit()

    resp = await client.get(f"/api/expenses/{first.id}", headers=_auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["is_potential_duplicate"] is True


async def test_a_lone_expense_is_never_flagged(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("dup-lone@example.com")
    user_id = await _get_user_id(client, token)

    expense = _seed(owner_session, user_id)
    await owner_session.commit()

    resp = await client.get(f"/api/expenses/{expense.id}", headers=_auth_headers(token))
    assert resp.json()["is_potential_duplicate"] is False


async def test_duplicate_flag_never_crosses_tenants(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    """Two different users' expenses can legitimately share vendor+date+total
    (same coffee shop, same day, same coincidental price) — that must never
    be flagged, since it isn't a duplicate FROM EITHER USER'S PERSPECTIVE."""
    from app.db.models.user import User

    other = User(email="dup-tenant-other@example.com", password_hash="not-a-real-hash")
    owner_session.add(other)
    await owner_session.flush()
    _seed(owner_session, other.id)

    token = await signup_user("dup-tenant-mine@example.com")
    user_id = await _get_user_id(client, token)
    _seed(owner_session, user_id)
    await owner_session.commit()

    resp = await client.get("/api/expenses", headers=_auth_headers(token))
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["is_potential_duplicate"] is False

from datetime import date, timedelta
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
        vendor="Test Vendor",
        category="Meals",
        currency="AUD",
        total=Decimal("10.00"),
        expense_date=None,
        status="ready",
    )
    defaults.update(overrides)
    expense = Expense(user_id=user_id, **defaults)
    owner_session.add(expense)
    return expense


async def test_filters_by_date_range(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("search-daterange@example.com")
    user_id = await _get_user_id(client, token)

    today = date.today()
    _seed(owner_session, user_id, vendor="In Range", expense_date=today)
    _seed(owner_session, user_id, vendor="Too Early", expense_date=today - timedelta(days=30))
    _seed(owner_session, user_id, vendor="Too Late", expense_date=today + timedelta(days=30))
    await owner_session.commit()

    resp = await client.get(
        "/api/expenses",
        params={
            "date_from": (today - timedelta(days=1)).isoformat(),
            "date_to": (today + timedelta(days=1)).isoformat(),
        },
        headers=_auth_headers(token),
    )

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["vendor"] == "In Range"


async def test_date_from_alone_is_an_open_ended_lower_bound(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("search-datefrom@example.com")
    user_id = await _get_user_id(client, token)

    today = date.today()
    _seed(owner_session, user_id, vendor="Recent", expense_date=today)
    _seed(owner_session, user_id, vendor="Old", expense_date=today - timedelta(days=100))
    await owner_session.commit()

    resp = await client.get(
        "/api/expenses",
        params={"date_from": (today - timedelta(days=1)).isoformat()},
        headers=_auth_headers(token),
    )

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["vendor"] == "Recent"


async def test_filters_by_category(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("search-category@example.com")
    user_id = await _get_user_id(client, token)

    _seed(owner_session, user_id, vendor="A Meal", category="Meals")
    _seed(owner_session, user_id, vendor="Some Software", category="Software")
    await owner_session.commit()

    resp = await client.get(
        "/api/expenses", params={"category": "Software"}, headers=_auth_headers(token)
    )

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["vendor"] == "Some Software"


async def test_rejects_an_invalid_category_filter(client: AsyncClient, signup_user) -> None:
    token = await signup_user("search-bad-category@example.com")

    resp = await client.get(
        "/api/expenses", params={"category": "Not A Real Category"}, headers=_auth_headers(token)
    )

    assert resp.status_code == 422


async def test_free_text_vendor_search_is_case_insensitive_and_partial(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("search-vendor@example.com")
    user_id = await _get_user_id(client, token)

    _seed(owner_session, user_id, vendor="Corner Cafe")
    _seed(owner_session, user_id, vendor="Other Shop")
    await owner_session.commit()

    resp = await client.get("/api/expenses", params={"q": "corner"}, headers=_auth_headers(token))

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["vendor"] == "Corner Cafe"


async def test_vendor_search_escapes_like_wildcards(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("search-wildcard@example.com")
    user_id = await _get_user_id(client, token)

    _seed(owner_session, user_id, vendor="50% Off Store")
    _seed(owner_session, user_id, vendor="Fifty Off Store")
    await owner_session.commit()

    resp = await client.get("/api/expenses", params={"q": "50%"}, headers=_auth_headers(token))

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["vendor"] == "50% Off Store"


async def test_filters_compose_together(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("search-compose@example.com")
    user_id = await _get_user_id(client, token)

    today = date.today()
    _seed(
        owner_session,
        user_id,
        vendor="Corner Cafe",
        category="Meals",
        status="confirmed",
        expense_date=today,
    )
    # Wrong category, otherwise matching — must be excluded.
    _seed(
        owner_session,
        user_id,
        vendor="Corner Cafe",
        category="Software",
        status="confirmed",
        expense_date=today,
    )
    # Wrong status, otherwise matching — must be excluded.
    _seed(
        owner_session,
        user_id,
        vendor="Corner Cafe",
        category="Meals",
        status="ready",
        expense_date=today,
    )
    await owner_session.commit()

    resp = await client.get(
        "/api/expenses",
        params={"q": "corner", "category": "Meals", "status": "confirmed"},
        headers=_auth_headers(token),
    )

    body = resp.json()
    assert body["total"] == 1

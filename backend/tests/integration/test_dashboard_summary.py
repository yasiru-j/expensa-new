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
        status="confirmed",
    )
    defaults.update(overrides)
    expense = Expense(user_id=user_id, **defaults)
    owner_session.add(expense)
    return expense


def _by_currency(items: list[dict]) -> dict[str, str]:
    return {item["currency"]: item["total"] for item in items}


async def test_summary_with_no_data_returns_empty_aggregates(
    client: AsyncClient, signup_user
) -> None:
    token = await signup_user("dashboard-empty@example.com")

    resp = await client.get("/api/dashboard/summary", headers=_auth_headers(token))

    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "month_to_date": [],
        "receipt_count": 0,
        "by_category": [],
        "by_month": [],
    }


async def test_month_to_date_only_counts_current_month_and_confirmed(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("dashboard-mtd@example.com")
    user_id = await _get_user_id(client, token)

    today = date.today()
    last_month_day = today.replace(day=1) - timedelta(days=1)

    _seed(owner_session, user_id, total=Decimal("50.00"), expense_date=today, status="confirmed")
    _seed(
        owner_session,
        user_id,
        total=Decimal("999.00"),
        expense_date=last_month_day,
        status="confirmed",
    )
    _seed(owner_session, user_id, total=Decimal("30.00"), expense_date=today, status="ready")
    await owner_session.commit()

    resp = await client.get("/api/dashboard/summary", headers=_auth_headers(token))

    assert resp.status_code == 200
    assert _by_currency(resp.json()["month_to_date"]) == {"AUD": "50.00"}


async def test_receipt_count_only_counts_confirmed_rows(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("dashboard-count@example.com")
    user_id = await _get_user_id(client, token)

    _seed(owner_session, user_id, status="confirmed")
    _seed(owner_session, user_id, status="confirmed")
    _seed(owner_session, user_id, status="ready")
    _seed(owner_session, user_id, status="failed")
    _seed(owner_session, user_id, status="processing")
    await owner_session.commit()

    resp = await client.get("/api/dashboard/summary", headers=_auth_headers(token))

    assert resp.json()["receipt_count"] == 2


async def test_by_category_aggregates_totals_and_counts(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("dashboard-category@example.com")
    user_id = await _get_user_id(client, token)

    _seed(owner_session, user_id, category="Meals", total=Decimal("10.00"))
    _seed(owner_session, user_id, category="Meals", total=Decimal("15.00"))
    _seed(owner_session, user_id, category="Software", total=Decimal("99.00"))
    # Not confirmed — must not contribute.
    _seed(owner_session, user_id, category="Meals", total=Decimal("500.00"), status="ready")
    await owner_session.commit()

    resp = await client.get("/api/dashboard/summary", headers=_auth_headers(token))

    by_category = {item["category"]: item for item in resp.json()["by_category"]}
    assert by_category["Meals"]["total"] == "25.00"
    assert by_category["Meals"]["count"] == 2
    assert by_category["Software"]["total"] == "99.00"
    assert by_category["Software"]["count"] == 1


async def test_currency_grouping_does_not_sum_across_currencies(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("dashboard-currency@example.com")
    user_id = await _get_user_id(client, token)

    today = date.today()
    _seed(owner_session, user_id, currency="AUD", total=Decimal("100.00"), expense_date=today)
    _seed(owner_session, user_id, currency="USD", total=Decimal("40.00"), expense_date=today)
    await owner_session.commit()

    resp = await client.get("/api/dashboard/summary", headers=_auth_headers(token))
    body = resp.json()

    # Two distinct currency entries, never one summed 140.00 across currencies.
    assert _by_currency(body["month_to_date"]) == {"AUD": "100.00", "USD": "40.00"}

    category_currencies = _by_currency(body["by_category"])
    assert category_currencies == {"AUD": "100.00", "USD": "40.00"}


async def test_by_month_is_grouped_and_windowed(
    client: AsyncClient, signup_user, owner_session: AsyncSession
) -> None:
    token = await signup_user("dashboard-bymonth@example.com")
    user_id = await _get_user_id(client, token)

    today = date.today()
    two_months_ago = (today.replace(day=1) - timedelta(days=32)).replace(day=1)
    far_past = (today.replace(day=1) - timedelta(days=400)).replace(day=1)

    _seed(owner_session, user_id, total=Decimal("10.00"), expense_date=today)
    _seed(owner_session, user_id, total=Decimal("20.00"), expense_date=two_months_ago)
    _seed(owner_session, user_id, total=Decimal("30.00"), expense_date=far_past)
    _seed(owner_session, user_id, total=Decimal("40.00"), expense_date=None)  # no date, excluded
    await owner_session.commit()

    resp = await client.get(
        "/api/dashboard/summary", params={"months": 3}, headers=_auth_headers(token)
    )
    months = {item["month"]: item["total"] for item in resp.json()["by_month"]}

    assert months[today.strftime("%Y-%m")] == "10.00"
    assert months[two_months_ago.strftime("%Y-%m")] == "20.00"
    # Older than the 3-month window, and the null-date row (nothing to bucket
    # it under) — neither shows up anywhere in the series.
    assert far_past.strftime("%Y-%m") not in months
    assert "40.00" not in months.values()

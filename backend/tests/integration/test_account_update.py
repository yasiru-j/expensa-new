"""PATCH /api/account — updates account-profile fields (currently just
full_name). Always scoped to the caller via the JWT, never a client-supplied
id — see app/api/account.py for why that matters (the users table has no
RLS policy of its own)."""

from httpx import AsyncClient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_update_account_sets_full_name(client: AsyncClient, signup_user) -> None:
    token = await signup_user("patch-name@example.com")

    resp = await client.patch(
        "/api/account", json={"full_name": "Pat Chname"}, headers=_auth_headers(token)
    )

    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Pat Chname"

    me = await client.get("/api/auth/me", headers=_auth_headers(token))
    assert me.json()["full_name"] == "Pat Chname"


async def test_update_account_can_clear_full_name(client: AsyncClient, signup_user) -> None:
    token = await signup_user("clear-name@example.com")
    headers = _auth_headers(token)
    await client.patch("/api/account", json={"full_name": "Someone"}, headers=headers)

    resp = await client.patch("/api/account", json={"full_name": None}, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["full_name"] is None


async def test_update_account_omitting_full_name_leaves_it_unchanged(
    client: AsyncClient, signup_user
) -> None:
    token = await signup_user("omit-name@example.com")
    await client.patch("/api/account", json={"full_name": "Kept"}, headers=_auth_headers(token))

    resp = await client.patch("/api/account", json={}, headers=_auth_headers(token))

    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Kept"


async def test_update_account_blank_full_name_is_stored_as_null(
    client: AsyncClient, signup_user
) -> None:
    token = await signup_user("blank-name@example.com")

    resp = await client.patch(
        "/api/account", json={"full_name": "   "}, headers=_auth_headers(token)
    )

    assert resp.status_code == 200
    assert resp.json()["full_name"] is None


async def test_update_account_requires_auth(client: AsyncClient) -> None:
    resp = await client.patch("/api/account", json={"full_name": "No Auth"})

    assert resp.status_code == 401

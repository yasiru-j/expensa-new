import asyncio

from httpx import AsyncClient

from app.core.config import get_settings

REFRESH_COOKIE = "refresh_token"
settings = get_settings()


async def test_signup_returns_access_token_and_sets_refresh_cookie(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/signup", json={"email": "alice@example.com", "password": "hunter22222"}
    )

    assert resp.status_code == 201
    assert "access_token" in resp.json()
    assert REFRESH_COOKIE in resp.cookies

    set_cookie = resp.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie or "samesite=lax" in set_cookie.lower()


async def test_signup_rejects_duplicate_email(client: AsyncClient) -> None:
    payload = {"email": "bob@example.com", "password": "hunter22222"}
    await client.post("/api/auth/signup", json=payload)

    resp = await client.post("/api/auth/signup", json=payload)

    assert resp.status_code == 409


async def test_signup_stores_optional_full_name(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/signup",
        json={
            "email": "jan@example.com",
            "password": "hunter22222",
            "full_name": "Jan Example",
        },
    )
    access_token = resp.json()["access_token"]

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me.json()["full_name"] == "Jan Example"


async def test_signup_without_full_name_leaves_it_null(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/signup", json={"email": "kim@example.com", "password": "hunter22222"}
    )
    access_token = resp.json()["access_token"]

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me.json()["full_name"] is None


async def test_login_with_correct_credentials_succeeds(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/signup", json={"email": "carol@example.com", "password": "hunter22222"}
    )

    resp = await client.post(
        "/api/auth/login", json={"email": "carol@example.com", "password": "hunter22222"}
    )

    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_with_wrong_password_is_rejected(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/signup", json={"email": "dave@example.com", "password": "hunter22222"}
    )

    resp = await client.post(
        "/api/auth/login", json={"email": "dave@example.com", "password": "wrong-password"}
    )

    assert resp.status_code == 401


async def test_protected_route_rejects_missing_token(client: AsyncClient) -> None:
    resp = await client.get("/api/auth/me")

    assert resp.status_code == 401


async def test_protected_route_accepts_valid_access_token(client: AsyncClient) -> None:
    signup = await client.post(
        "/api/auth/signup", json={"email": "erin@example.com", "password": "hunter22222"}
    )
    access_token = signup.json()["access_token"]

    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})

    assert resp.status_code == 200
    assert resp.json()["email"] == "erin@example.com"


async def test_refresh_rotates_the_access_token(client: AsyncClient) -> None:
    signup = await client.post(
        "/api/auth/signup", json={"email": "frank@example.com", "password": "hunter22222"}
    )
    original_access_token = signup.json()["access_token"]

    resp = await client.post("/api/auth/refresh")

    assert resp.status_code == 200
    assert resp.json()["access_token"] != original_access_token


async def test_concurrent_refresh_with_same_token_does_not_log_the_session_out(
    client: AsyncClient,
) -> None:
    """Regression test for the real bug this rotation policy exists to fix:
    two refresh requests firing at once with the same starting cookie (a
    React StrictMode double-effect, two tabs loading together, a retried
    request) must not log the user out. Exactly one rotation happens —
    the other request gets that same result back, not a second rotation
    and not a 401."""
    await client.post(
        "/api/auth/signup", json={"email": "ivan@example.com", "password": "hunter22222"}
    )

    first, second = await asyncio.gather(
        client.post("/api/auth/refresh"),
        client.post("/api/auth/refresh"),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    # Both requests observed the SAME rotation, not two independent ones.
    assert first.json()["access_token"] == second.json()["access_token"]
    assert first.cookies.get(REFRESH_COOKIE) == second.cookies.get(REFRESH_COOKIE)

    # And the session keeps working afterward with the tokens it got back.
    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {first.json()['access_token']}"}
    )
    assert me.status_code == 200


async def test_refresh_token_replay_within_grace_window_is_allowed(client: AsyncClient) -> None:
    """A sequential (non-concurrent) replay shortly after rotation is
    exactly the same case as the concurrent one above, just spaced out —
    still within the grace window, still allowed, still the same result."""
    await client.post(
        "/api/auth/signup", json={"email": "grace@example.com", "password": "hunter22222"}
    )
    old_refresh_cookie = client.cookies.get(REFRESH_COOKIE)

    first = await client.post("/api/auth/refresh")
    assert first.status_code == 200

    client.cookies.set(REFRESH_COOKIE, old_refresh_cookie)
    replay = await client.post("/api/auth/refresh")

    assert replay.status_code == 200
    assert replay.json()["access_token"] == first.json()["access_token"]


async def test_refresh_token_replay_outside_grace_window_is_rejected(
    client: AsyncClient,
) -> None:
    """Theft-detection guarantee: once the grace window has elapsed, a
    replayed pre-rotation token is dead — same as strict single-use."""
    await client.post(
        "/api/auth/signup", json={"email": "heidi-replay@example.com", "password": "hunter22222"}
    )
    old_refresh_cookie = client.cookies.get(REFRESH_COOKIE)

    first = await client.post("/api/auth/refresh")
    assert first.status_code == 200

    await asyncio.sleep(settings.refresh_token_reuse_grace_seconds + 0.5)

    client.cookies.set(REFRESH_COOKIE, old_refresh_cookie)
    replay = await client.post("/api/auth/refresh")

    assert replay.status_code == 401


async def test_logout_revokes_the_refresh_token(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/signup", json={"email": "heidi@example.com", "password": "hunter22222"}
    )

    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 200

    resp = await client.post("/api/auth/refresh")
    assert resp.status_code == 401

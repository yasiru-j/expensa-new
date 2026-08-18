from httpx import AsyncClient

REFRESH_COOKIE = "refresh_token"


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


async def test_refresh_token_is_single_use(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/signup", json={"email": "grace@example.com", "password": "hunter22222"}
    )
    old_refresh_cookie = client.cookies.get(REFRESH_COOKIE)

    first = await client.post("/api/auth/refresh")
    assert first.status_code == 200

    # Replay the pre-rotation refresh token — it must already be dead.
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

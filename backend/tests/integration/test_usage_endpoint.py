from httpx import AsyncClient

from tests.factories import fake_receipt_response, make_test_image_bytes


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_usage_starts_at_zero(client: AsyncClient, signup_user) -> None:
    token = await signup_user("usage-zero@example.com")

    resp = await client.get("/api/usage", headers=_auth_headers(token))

    assert resp.status_code == 200
    body = resp.json()
    assert body["extraction_count"] == 0
    assert body["monthly_limit"] > 0
    assert body["remaining"] == body["monthly_limit"]
    assert "period_month" in body


async def test_usage_reflects_a_successful_upload(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("usage-after-upload@example.com")
    mock_openai_client.chat.completions.create.return_value = fake_receipt_response()

    await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", make_test_image_bytes(), "image/jpeg")},
        headers=_auth_headers(token),
    )

    resp = await client.get("/api/usage", headers=_auth_headers(token))
    body = resp.json()
    assert body["extraction_count"] == 1
    assert body["remaining"] == body["monthly_limit"] - 1


async def test_usage_requires_authentication(client: AsyncClient) -> None:
    resp = await client.get("/api/usage")

    assert resp.status_code == 401


async def test_usage_is_owner_scoped(client: AsyncClient, signup_user, mock_openai_client) -> None:
    token_a = await signup_user("usage-owner-a@example.com")
    token_b = await signup_user("usage-owner-b@example.com")
    mock_openai_client.chat.completions.create.return_value = fake_receipt_response()

    await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", make_test_image_bytes(), "image/jpeg")},
        headers=_auth_headers(token_b),
    )

    resp_a = await client.get("/api/usage", headers=_auth_headers(token_a))
    assert resp_a.json()["extraction_count"] == 0  # user B's upload doesn't leak into A's usage

    resp_b = await client.get("/api/usage", headers=_auth_headers(token_b))
    assert resp_b.json()["extraction_count"] == 1

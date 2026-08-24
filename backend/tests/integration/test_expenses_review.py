import random

from httpx import AsyncClient

from tests.factories import fake_receipt_response, make_test_image_bytes


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _upload_ready_expense(
    client: AsyncClient, mock_openai_client, token: str, **overrides
) -> str:
    # A fresh, distinctly-colored image per call — sharing one fixed image
    # across multiple uploads in the same test would collide on file_hash
    # idempotency and silently return the SAME expense instead of a new one.
    image_bytes = make_test_image_bytes(
        color=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    )
    mock_openai_client.chat.completions.create.return_value = fake_receipt_response(**overrides)
    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", image_bytes, "image/jpeg")},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "ready", body
    return body["id"]


async def test_upload_populates_ai_sourced_provenance_for_every_tracked_field(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("review-provenance@example.com")
    expense_id = await _upload_ready_expense(
        client, mock_openai_client, token, vendor="Corner Cafe"
    )

    detail = await client.get(f"/api/expenses/{expense_id}", headers=_auth_headers(token))
    provenance = detail.json()["field_provenance"]

    assert provenance["vendor"]["source"] == "ai"
    assert provenance["vendor"]["ai_value"] == "Corner Cafe"
    assert provenance["vendor"]["confidence"] is not None


async def test_patch_updates_field_and_flips_its_provenance_to_user(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("review-patch@example.com")
    expense_id = await _upload_ready_expense(
        client, mock_openai_client, token, vendor="Corner Cafe"
    )

    patch = await client.patch(
        f"/api/expenses/{expense_id}",
        json={"vendor": "Corrected Vendor Name"},
        headers=_auth_headers(token),
    )

    assert patch.status_code == 200, patch.text
    body = patch.json()
    assert body["vendor"] == "Corrected Vendor Name"
    assert body["field_provenance"]["vendor"]["source"] == "user"
    # The original AI answer is preserved, not overwritten.
    assert body["field_provenance"]["vendor"]["ai_value"] == "Corner Cafe"
    # Untouched fields stay AI-sourced.
    assert body["field_provenance"]["total"]["source"] == "ai"


async def test_patch_only_flips_provenance_for_fields_actually_sent(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("review-partial-patch@example.com")
    expense_id = await _upload_ready_expense(client, mock_openai_client, token)

    patch = await client.patch(
        f"/api/expenses/{expense_id}",
        json={"category": "Software"},
        headers=_auth_headers(token),
    )

    body = patch.json()
    assert body["category"] == "Software"
    assert body["field_provenance"]["category"]["source"] == "user"
    for field_name in ("vendor", "total", "currency", "payment_method"):
        assert body["field_provenance"][field_name]["source"] == "ai"


async def test_patch_can_explicitly_clear_a_field_to_null(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("review-clear-field@example.com")
    expense_id = await _upload_ready_expense(
        client, mock_openai_client, token, vendor="Corner Cafe"
    )

    patch = await client.patch(
        f"/api/expenses/{expense_id}",
        json={"vendor": None},
        headers=_auth_headers(token),
    )

    assert patch.status_code == 200
    body = patch.json()
    assert body["vendor"] is None
    assert body["field_provenance"]["vendor"]["source"] == "user"


async def test_patch_rejects_an_invalid_category(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("review-bad-category@example.com")
    expense_id = await _upload_ready_expense(client, mock_openai_client, token)

    patch = await client.patch(
        f"/api/expenses/{expense_id}",
        json={"category": "Not A Real Category"},
        headers=_auth_headers(token),
    )

    assert patch.status_code == 422


async def test_patch_rejects_an_invalid_currency(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("review-bad-currency@example.com")
    expense_id = await _upload_ready_expense(client, mock_openai_client, token)

    patch = await client.patch(
        f"/api/expenses/{expense_id}",
        json={"currency": "nope"},
        headers=_auth_headers(token),
    )

    assert patch.status_code == 422


async def test_patch_rejects_editing_a_non_ready_expense(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("review-patch-wrong-status@example.com")
    expense_id = await _upload_ready_expense(client, mock_openai_client, token)

    confirm = await client.post(f"/api/expenses/{expense_id}/confirm", headers=_auth_headers(token))
    assert confirm.status_code == 200

    patch = await client.patch(
        f"/api/expenses/{expense_id}",
        json={"vendor": "Too Late"},
        headers=_auth_headers(token),
    )

    assert patch.status_code == 409


async def test_confirm_transitions_ready_to_confirmed(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("review-confirm@example.com")
    expense_id = await _upload_ready_expense(client, mock_openai_client, token)

    confirm = await client.post(f"/api/expenses/{expense_id}/confirm", headers=_auth_headers(token))

    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"

    detail = await client.get(f"/api/expenses/{expense_id}", headers=_auth_headers(token))
    assert detail.json()["status"] == "confirmed"


async def test_confirm_rejects_a_non_ready_expense(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("review-confirm-twice@example.com")
    expense_id = await _upload_ready_expense(client, mock_openai_client, token)

    first = await client.post(f"/api/expenses/{expense_id}/confirm", headers=_auth_headers(token))
    assert first.status_code == 200

    second = await client.post(f"/api/expenses/{expense_id}/confirm", headers=_auth_headers(token))
    assert second.status_code == 409


async def test_list_can_be_filtered_by_status(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("review-status-filter@example.com")
    ready_only_id = await _upload_ready_expense(
        client, mock_openai_client, token, vendor="Still Ready"
    )

    confirmed_id = await _upload_ready_expense(
        client, mock_openai_client, token, vendor="Now Confirmed"
    )
    await client.patch(
        f"/api/expenses/{confirmed_id}",
        json={"vendor": "Now Confirmed (edited)"},
        headers=_auth_headers(token),
    )
    await client.post(f"/api/expenses/{confirmed_id}/confirm", headers=_auth_headers(token))

    confirmed_only = await client.get(
        "/api/expenses", params={"status": "confirmed"}, headers=_auth_headers(token)
    )
    assert confirmed_only.status_code == 200
    confirmed_body = confirmed_only.json()
    assert confirmed_body["total"] == 1
    assert confirmed_body["items"][0]["id"] == confirmed_id

    ready_only = await client.get(
        "/api/expenses", params={"status": "ready"}, headers=_auth_headers(token)
    )
    ready_body = ready_only.json()
    assert ready_body["total"] == 1
    assert ready_body["items"][0]["id"] == ready_only_id

    unfiltered = await client.get("/api/expenses", headers=_auth_headers(token))
    assert unfiltered.json()["total"] == 2

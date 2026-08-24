from httpx import AsyncClient

from tests.factories import fake_openai_response, fake_receipt_response, make_test_image_bytes

IMAGE_BYTES = make_test_image_bytes()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_upload_extracts_and_persists_a_ready_expense(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("upload-happy@example.com")
    mock_openai_client.chat.completions.create.return_value = fake_receipt_response(
        vendor="Corner Cafe", total=22.00
    )

    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", IMAGE_BYTES, "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "ready"
    expense_id = body["id"]

    detail = await client.get(f"/api/expenses/{expense_id}", headers=_auth_headers(token))
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["vendor"] == "Corner Cafe"
    assert detail_body["status"] == "ready"
    assert len(detail_body["line_items"]) == 2
    assert detail_body["file_url"] is not None  # presigned URL was generated

    listing = await client.get("/api/expenses", headers=_auth_headers(token))
    assert listing.status_code == 200
    listing_body = listing.json()
    assert listing_body["total"] == 1
    assert listing_body["items"][0]["id"] == expense_id


async def test_upload_of_a_non_receipt_lands_status_failed(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("upload-nonreceipt@example.com")
    mock_openai_client.chat.completions.create.return_value = fake_receipt_response(
        is_receipt=False
    )

    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("not-a-receipt.jpg", IMAGE_BYTES, "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert resp.status_code == 201
    assert resp.json()["status"] == "failed"
    # Non-receipt is a hard rejection with no retry.
    assert mock_openai_client.chat.completions.create.call_count == 1


async def test_upload_with_malformed_model_response_lands_status_failed_after_retry(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("upload-malformed@example.com")
    mock_openai_client.chat.completions.create.side_effect = [
        fake_openai_response("not valid json"),
        fake_openai_response("still not valid json"),
    ]

    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", IMAGE_BYTES, "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "failed"
    assert mock_openai_client.chat.completions.create.call_count == 2

    # Never left stuck at `processing`.
    detail = await client.get(f"/api/expenses/{body['id']}", headers=_auth_headers(token))
    assert detail.json()["status"] == "failed"


async def test_upload_rejects_unsupported_file_type(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("upload-badtype@example.com")

    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("notes.txt", b"just some text, not an image", "text/plain")},
        headers=_auth_headers(token),
    )

    assert resp.status_code == 400
    # Rejected before any OpenAI call.
    mock_openai_client.chat.completions.create.assert_not_called()


async def test_upload_ignores_a_spoofed_content_type_header(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    """A client claiming image/jpeg for plain text must be rejected — file type
    is sniffed from magic bytes, never trusted from the header."""
    token = await signup_user("upload-spoofed@example.com")

    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("fake.jpg", b"just some text, not an image", "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert resp.status_code == 400
    mock_openai_client.chat.completions.create.assert_not_called()


async def test_upload_rejects_oversized_file(
    client: AsyncClient, signup_user, mock_openai_client, monkeypatch
) -> None:
    monkeypatch.setattr("app.api.expenses.settings.max_upload_size_bytes", 100)
    token = await signup_user("upload-toobig@example.com")

    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", IMAGE_BYTES, "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert resp.status_code == 413
    mock_openai_client.chat.completions.create.assert_not_called()


async def test_upload_requires_authentication(client: AsyncClient, mock_openai_client) -> None:
    resp = await client.post(
        "/api/expenses/upload", files={"file": ("receipt.jpg", IMAGE_BYTES, "image/jpeg")}
    )

    assert resp.status_code == 401


async def test_reuploading_the_same_file_is_idempotent(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("upload-idempotent@example.com")
    mock_openai_client.chat.completions.create.return_value = fake_receipt_response(
        vendor="Corner Cafe"
    )

    first = await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", IMAGE_BYTES, "image/jpeg")},
        headers=_auth_headers(token),
    )
    second = await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", IMAGE_BYTES, "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    # The second upload must not re-invoke extraction.
    assert mock_openai_client.chat.completions.create.call_count == 1

    listing = await client.get("/api/expenses", headers=_auth_headers(token))
    assert listing.json()["total"] == 1


async def test_upload_survives_a_totally_unexpected_error_in_the_pipeline(
    client: AsyncClient, signup_user, mock_openai_client, monkeypatch
) -> None:
    """The upload handler's broad `except Exception` must catch failure types
    that aren't NonReceiptError/ExtractionFailedError too — e.g. a bug in
    image prep, or storage — and still land the row at `failed` rather than
    leaving it stuck at `processing`."""

    def _boom(*args, **kwargs):
        raise RuntimeError("totally unexpected failure, unrelated to extraction")

    monkeypatch.setattr("app.api.expenses.downscale_image", _boom)
    token = await signup_user("upload-unexpected-error@example.com")

    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", IMAGE_BYTES, "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "failed"

    detail = await client.get(f"/api/expenses/{body['id']}", headers=_auth_headers(token))
    assert detail.json()["status"] == "failed"
    # Never even reached the (mocked) OpenAI call.
    mock_openai_client.chat.completions.create.assert_not_called()

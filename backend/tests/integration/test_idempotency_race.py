"""Proves the unique partial index (migration 0003) + ON CONFLICT DO NOTHING
actually closes the Phase 2 race: two truly concurrent identical uploads
must collapse to exactly one row and one extraction, not two.
"""

import asyncio

from httpx import AsyncClient

from tests.factories import fake_openai_response, fake_receipt_response, make_test_image_bytes


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_concurrent_identical_uploads_collapse_to_one_row_one_extraction(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("idempotency-race@example.com")
    mock_openai_client.chat.completions.create.return_value = fake_receipt_response()
    image = make_test_image_bytes()

    responses = await asyncio.gather(
        *[
            client.post(
                "/api/expenses/upload",
                files={"file": ("receipt.jpg", image, "image/jpeg")},
                headers=_auth_headers(token),
            )
            for _ in range(5)
        ]
    )

    for resp in responses:
        assert resp.status_code == 201, resp.text

    ids = {resp.json()["id"] for resp in responses}
    assert len(ids) == 1  # every request resolved to the SAME row

    assert mock_openai_client.chat.completions.create.call_count == 1

    listing = await client.get("/api/expenses", headers=_auth_headers(token))
    assert listing.json()["total"] == 1


async def test_reuploading_a_failed_file_retries_rather_than_returning_the_stale_row(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    """The unique index deliberately excludes status='failed', so a previous
    failure doesn't permanently block a fresh attempt at the same file."""
    token = await signup_user("idempotency-retry-after-failure@example.com")
    image = make_test_image_bytes()

    mock_openai_client.chat.completions.create.side_effect = [
        fake_openai_response("not valid json"),
        fake_openai_response("still not valid json"),
    ]
    first = await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", image, "image/jpeg")},
        headers=_auth_headers(token),
    )
    assert first.json()["status"] == "failed"

    mock_openai_client.chat.completions.create.side_effect = None
    mock_openai_client.chat.completions.create.return_value = fake_receipt_response()
    second = await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", image, "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert second.status_code == 201
    assert second.json()["status"] == "ready"
    assert second.json()["id"] != first.json()["id"]  # a genuinely new row/attempt

    listing = await client.get("/api/expenses", headers=_auth_headers(token))
    assert listing.json()["total"] == 2  # the failed row and the new ready row both exist

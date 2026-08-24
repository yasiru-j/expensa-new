"""The security gate for Phase 5: proves the guardrail order (auth -> rate
limit -> quota -> file validation -> extract) actually holds, and that
quota is charged exactly when it should be — never earlier, never later.
"""

import asyncio
from unittest.mock import AsyncMock

from httpx import AsyncClient

from tests.factories import fake_openai_response, fake_receipt_response, make_test_image_bytes


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _usage(client: AsyncClient, token: str) -> dict:
    resp = await client.get("/api/usage", headers=_auth_headers(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_rate_limit_blocks_before_any_openai_call(
    client: AsyncClient, signup_user, mock_openai_client, monkeypatch
) -> None:
    monkeypatch.setattr("app.api.expenses.settings.upload_rate_limit_per_hour", 2)
    monkeypatch.setattr("app.api.expenses.settings.rate_limit_window_seconds", 3600)
    token = await signup_user("guardrail-ratelimit@example.com")

    # Garbage bytes are fine — rate limiting rejects before the file is ever read.
    garbage = b"not a real file"
    for _ in range(2):
        resp = await client.post(
            "/api/expenses/upload",
            files={"file": ("x.jpg", garbage, "image/jpeg")},
            headers=_auth_headers(token),
        )
        assert resp.status_code in (201, 400)  # both consume the rate-limit slot either way

    third = await client.post(
        "/api/expenses/upload",
        files={"file": ("x.jpg", garbage, "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert third.status_code == 429
    assert "Retry-After" in third.headers
    mock_openai_client.chat.completions.create.assert_not_called()


async def test_quota_early_check_blocks_before_file_validation_or_minio(
    client: AsyncClient, signup_user, mock_openai_client, monkeypatch
) -> None:
    monkeypatch.setattr("app.api.expenses.settings.monthly_extraction_quota", 1)
    token = await signup_user("guardrail-quota-early@example.com")
    mock_openai_client.chat.completions.create.return_value = fake_receipt_response()

    first = await client.post(
        "/api/expenses/upload",
        files={"file": ("first.jpg", make_test_image_bytes(color=(1, 2, 3)), "image/jpeg")},
        headers=_auth_headers(token),
    )
    assert first.status_code == 201
    assert first.json()["status"] == "ready"
    assert mock_openai_client.chat.completions.create.call_count == 1

    mock_put_object = AsyncMock()
    monkeypatch.setattr("app.api.expenses.put_object", mock_put_object)

    second = await client.post(
        "/api/expenses/upload",
        # Even an outright unsupported file type — the quota gate must fire
        # first and never let this reach file-type validation at all.
        files={"file": ("second.txt", b"plain text", "text/plain")},
        headers=_auth_headers(token),
    )

    assert second.status_code == 429
    assert "quota" in second.json()["detail"].lower()
    assert mock_openai_client.chat.completions.create.call_count == 1  # unchanged
    mock_put_object.assert_not_called()


async def test_validation_rejected_upload_makes_zero_openai_calls_and_no_minio_write(
    client: AsyncClient, signup_user, mock_openai_client, monkeypatch
) -> None:
    token = await signup_user("guardrail-validation@example.com")
    mock_put_object = AsyncMock()
    monkeypatch.setattr("app.api.expenses.put_object", mock_put_object)

    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("notes.txt", b"just plain text", "text/plain")},
        headers=_auth_headers(token),
    )

    assert resp.status_code == 400
    mock_openai_client.chat.completions.create.assert_not_called()
    mock_put_object.assert_not_called()


async def test_validation_rejected_upload_does_not_consume_quota(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("guardrail-validation-quota@example.com")

    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("notes.txt", b"just plain text", "text/plain")},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 400

    usage = await _usage(client, token)
    assert usage["extraction_count"] == 0


async def test_failed_extraction_after_the_paid_call_still_consumes_quota(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("guardrail-failed-consumes@example.com")
    # Both tiers' both attempts come back malformed -> ExtractionFailedError,
    # but the call was made (and billed), so quota must still be charged.
    mock_openai_client.chat.completions.create.side_effect = [
        fake_openai_response("not valid json"),
        fake_openai_response("still not valid json"),
    ]

    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", make_test_image_bytes(), "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert resp.status_code == 201
    assert resp.json()["status"] == "failed"
    assert mock_openai_client.chat.completions.create.call_count == 2  # the internal retry

    usage = await _usage(client, token)
    assert usage["extraction_count"] == 1  # charged once for the one upload attempt


async def test_successful_extraction_consumes_quota_exactly_once(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("guardrail-success-consumes@example.com")
    mock_openai_client.chat.completions.create.return_value = fake_receipt_response()

    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", make_test_image_bytes(), "image/jpeg")},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "ready"

    usage = await _usage(client, token)
    assert usage["extraction_count"] == 1


async def test_reuploading_an_already_processed_file_does_not_consume_quota_again(
    client: AsyncClient, signup_user, mock_openai_client
) -> None:
    token = await signup_user("guardrail-idempotent-quota@example.com")
    mock_openai_client.chat.completions.create.return_value = fake_receipt_response()
    image = make_test_image_bytes()

    first = await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", image, "image/jpeg")},
        headers=_auth_headers(token),
    )
    second = await client.post(
        "/api/expenses/upload",
        files={"file": ("receipt.jpg", image, "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert first.json()["id"] == second.json()["id"]
    assert mock_openai_client.chat.completions.create.call_count == 1

    usage = await _usage(client, token)
    assert usage["extraction_count"] == 1


async def test_concurrent_cap_one_uploads_only_one_reaches_the_paid_call(
    client: AsyncClient, signup_user, mock_openai_client, monkeypatch
) -> None:
    monkeypatch.setattr("app.api.expenses.settings.monthly_extraction_quota", 1)
    token = await signup_user("guardrail-concurrent-quota@example.com")
    mock_openai_client.chat.completions.create.return_value = fake_receipt_response(vendor="Winner")

    image_a = make_test_image_bytes(color=(10, 20, 30))
    image_b = make_test_image_bytes(color=(200, 100, 50))

    responses = await asyncio.gather(
        client.post(
            "/api/expenses/upload",
            files={"file": ("a.jpg", image_a, "image/jpeg")},
            headers=_auth_headers(token),
        ),
        client.post(
            "/api/expenses/upload",
            files={"file": ("b.jpg", image_b, "image/jpeg")},
            headers=_auth_headers(token),
        ),
    )

    # Two valid outcomes depending on how the event loop happens to schedule
    # the two coroutines: either both get past the cheap early quota check
    # and race at the atomic increment-and-check gate (one 201 ready, one
    # 201 failed) — or the first request fully completes before the second's
    # early check even runs, so the second is rejected there instead (one
    # 201 ready, one 429). Both are correct and safe: never two paid calls,
    # never quota over-consumed. try_increment_usage's atomicity itself is
    # proven deterministically, without this scheduling ambiguity, by
    # test_quota.py's concurrent-race test at the DB layer directly.
    ready_responses = [
        r for r in responses if r.status_code == 201 and r.json()["status"] == "ready"
    ]
    other_responses = [r for r in responses if r not in ready_responses]
    assert len(ready_responses) == 1
    assert len(other_responses) == 1
    other = other_responses[0]
    assert (other.status_code, other.json().get("status")) in (
        (201, "failed"),
        (429, None),
    )

    assert mock_openai_client.chat.completions.create.call_count == 1

    usage = await _usage(client, token)
    assert usage["extraction_count"] == 1

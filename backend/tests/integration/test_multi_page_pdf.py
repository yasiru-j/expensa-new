"""GET /api/expenses/upload's dispatch decision for PDFs: single-page stays
inline (unchanged, existing behavior); a multi-page PDF (2..max_pdf_pages)
is enqueued to the async worker and the request returns immediately with
status="processing"; a PDF beyond max_pdf_pages is still rejected before
any paid call. The worker's own processing logic is covered separately in
test_worker.py — these tests only exercise the request/dispatch boundary.
"""

from unittest.mock import AsyncMock

from httpx import AsyncClient

from tests.factories import fake_receipt_response, make_test_pdf_bytes


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _mock_pool(monkeypatch) -> AsyncMock:
    pool = AsyncMock()

    async def _get_pool():
        return pool

    monkeypatch.setattr("app.api.expenses.get_arq_pool", _get_pool)
    return pool


async def test_multi_page_pdf_is_dispatched_async_and_never_calls_openai(
    client: AsyncClient, signup_user, mock_openai_client, monkeypatch
) -> None:
    pool = _mock_pool(monkeypatch)
    token = await signup_user("multipage-dispatch@example.com")
    me = await client.get("/api/auth/me", headers=_auth_headers(token))
    user_id = me.json()["id"]

    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("multi.pdf", make_test_pdf_bytes(pages=3), "application/pdf")},
        headers=_auth_headers(token),
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "processing"
    mock_openai_client.chat.completions.create.assert_not_called()

    pool.enqueue_job.assert_called_once()
    args = pool.enqueue_job.call_args.args
    assert args[0] == "process_multi_page_pdf"
    assert args[1] == resp.json()["id"]
    assert args[2] == user_id


async def test_pdf_beyond_the_page_limit_is_rejected_before_dispatch(
    client: AsyncClient, signup_user, mock_openai_client, monkeypatch
) -> None:
    monkeypatch.setattr("app.api.expenses.settings.max_pdf_pages", 5)
    pool = _mock_pool(monkeypatch)
    token = await signup_user("multipage-toolong@example.com")

    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("huge.pdf", make_test_pdf_bytes(pages=6), "application/pdf")},
        headers=_auth_headers(token),
    )

    assert resp.status_code == 400
    mock_openai_client.chat.completions.create.assert_not_called()
    pool.enqueue_job.assert_not_called()


async def test_single_page_pdf_still_processes_inline(
    client: AsyncClient, signup_user, mock_openai_client, monkeypatch
) -> None:
    pool = _mock_pool(monkeypatch)
    mock_openai_client.chat.completions.create.return_value = fake_receipt_response()
    token = await signup_user("multipage-singlepage@example.com")

    resp = await client.post(
        "/api/expenses/upload",
        files={"file": ("single.pdf", make_test_pdf_bytes(pages=1), "application/pdf")},
        headers=_auth_headers(token),
    )

    assert resp.status_code == 201
    assert resp.json()["status"] == "ready"
    mock_openai_client.chat.completions.create.assert_called_once()
    pool.enqueue_job.assert_not_called()


async def test_multi_page_pdf_does_not_consume_quota_on_the_request_path(
    client: AsyncClient, signup_user, mock_openai_client, monkeypatch
) -> None:
    """Quota for a multi-page PDF is charged inside the worker job, not on
    the request path — the request only enqueues."""
    _mock_pool(monkeypatch)
    token = await signup_user("multipage-quota@example.com")

    await client.post(
        "/api/expenses/upload",
        files={"file": ("multi.pdf", make_test_pdf_bytes(pages=2), "application/pdf")},
        headers=_auth_headers(token),
    )

    usage = await client.get("/api/usage", headers=_auth_headers(token))
    assert usage.json()["extraction_count"] == 0

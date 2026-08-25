# Expensa

AI-powered invoice/receipt extraction with a multi-user expense dashboard.

Full spec: [docs/PRD.md](docs/PRD.md), [docs/TRD.md](docs/TRD.md), [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).

## Stack

- **Backend:** FastAPI (Python 3.12), async, SQLAlchemy 2.0 + Alembic, Postgres
- **Auth:** JWT (access + refresh), bcrypt, Google OAuth via Authlib
- **Frontend:** React (Vite) + Tailwind + Recharts
- **Storage:** S3-compatible (MinIO locally); Redis for jobs/rate limiting

## Local setup

1. Copy `.env.example` to `.env` and fill in real values (never commit `.env`).
2. `docker-compose up` — brings up Postgres, Redis, MinIO, the backend, and the frontend.
   The backend container runs `alembic upgrade head` on startup before serving.
3. Backend: http://localhost:8000/health · Frontend: http://localhost:5173

### Running the backend outside Docker

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

### Running the frontend outside Docker

```bash
cd frontend
npm install
npm run dev
```

### Tests

Tests run against a real Postgres database (RLS can't be verified against a mock), using a
throwaway `<db>_test` database that's dropped and recreated each run. Postgres must be reachable
(e.g. `docker-compose up -d postgres`).

```bash
cd backend
pytest
```

The security suite (`tests/security/test_rls_isolation.py`) proves that one user cannot read,
update, delete, or insert another user's rows — even with no `WHERE user_id = ...` filter —
because Postgres Row-Level Security enforces it at the database layer.

### Linting

```bash
cd backend && ruff check . && black --check .
cd frontend && npm run lint
```

## Security model

- Every authenticated request scopes its database transaction to the caller via
  `SET LOCAL app.user_id`, read by Postgres RLS policies on `expenses`, `line_items`, and `usage`.
- The API connects as a restricted `expensa_app` role (created by the first migration) that is
  **not** the table owner and **not** a superuser — both would silently bypass RLS. Migrations run
  under a separate owner role.
- Access tokens live in memory on the client only; refresh tokens are httpOnly, Secure (in
  production), SameSite cookies, rotated (single-use) on every refresh.
- The OpenAI API key and all extraction calls run server-side only.

## Cost control & guardrails

Every upload passes through these, **in this order**, before any paid OpenAI call is made:

1. **Auth** — JWT required.
2. **Rate limit** — Redis-backed sliding window, per user, on `/api/expenses/upload`
   (`UPLOAD_RATE_LIMIT_PER_HOUR`, default 20/hour). Exceeding it returns `429` with a
   `Retry-After` header.
3. **Quota** — a cheap, non-authoritative check against the `usage` table
   (`MONTHLY_EXTRACTION_QUOTA`, default 50/month) rejects fast if the caller is already over.
   The **authoritative** gate is a single atomic `INSERT ... ON CONFLICT ... WHERE count < limit`
   immediately before the paid call — two concurrent requests at the last slot can't both win,
   because they serialize on the same database row rather than racing a read-then-write.
4. **File validation** — type (sniffed from magic bytes, not the client-declared
   `Content-Type`), size (`MAX_UPLOAD_SIZE_BYTES`), and page count (`MAX_PDF_PAGES`), all before
   any network call.
5. **Extract** — cheap model first (`OPENAI_EXTRACTION_MODEL`); escalates once to a larger model
   (`OPENAI_EXTRACTION_MODEL_ESCALATED`) only if the cheap model's own confidence is below
   `MODEL_TIER_CONFIDENCE_THRESHOLD` or server-side validation flags an issue. Quota is
   incremented exactly once per upload attempt, regardless of how many underlying model calls
   that involves.

**Idempotency**: a unique partial index on `(user_id, file_hash) WHERE status <> 'failed'`
means concurrent identical uploads collapse to one row and one extraction — the database
resolves the race, not a check in application code. A previously **failed** upload is
excluded from that constraint on purpose, so re-uploading the same file after a failure
retries rather than returning the stale failure.

**Stuck rows**: there's no background worker in this app yet (extraction is inline and
synchronous), so a row that gets stuck at `processing` — a crash between the two upload
transactions — is swept to `failed` opportunistically on the next upload or list request for
that user, once it's older than `STALE_PROCESSING_MINUTES` (default 15). See
`app/db/maintenance.py` for why this is a swept-on-read check rather than a scheduled job.

## Export

`GET /api/export` streams the caller's expenses as CSV or Excel (XLSX), owner-scoped via
RLS and filtered identically to `GET /api/expenses` — both build their `WHERE` clause from
the same `build_expense_conditions` helper, so the exported rows can never drift from what
the table is currently showing for the same `status` / `date_from` / `date_to` / `category` /
`q` params.

- **Format**: a `format=csv|xlsx` query param (default `csv`) — not `Accept`-header content
  negotiation, for consistency with every other filter on this API already being a query
  param, and so the export is a plain linkable/downloadable URL.
- **Currency**: every row includes its `currency` column explicitly. A totals block is
  appended after the data rows, grouped by currency (e.g. `TOTAL (AUD)`, `TOTAL (USD)`) —
  amounts are never summed across different currencies into one number, matching the
  dashboard's per-currency aggregates.
- **Numbers**: money fields are rendered from `Decimal` with `format(value, "f")` — fixed
  notation, no scientific notation, no float artifacts (e.g. `12.34`, never `12.340000001`
  or a locale thousands separator).
- **CSV injection**: a text field (`vendor`, `vendor_tax_id`, `payment_method`) whose value
  starts with `=`, `+`, `-`, or `@` is prefixed with a leading apostrophe before being
  written — the same thing Excel does when a user manually types a value that looks like a
  formula. This defuses formula/DDE injection from a crafted vendor name without altering
  the visible text. Applied to both formats, though XLSX cell values written by openpyxl are
  already typed as plain strings (not formulas) so they weren't executable there either.
- **Encoding**: the CSV is UTF-8 with a leading BOM so Excel opens non-ASCII vendor names
  (e.g. "Café", "日本語") correctly instead of mangling them.
- **Line items**: excluded from the flat CSV (they don't fit a "one row per expense" shape
  without duplicating expense rows) but included in the XLSX as a second "Line Items" sheet,
  keyed by `expense_id` — no data is silently dropped from the richer format.
- **Streaming**: CSV is genuinely streamed row-by-row, batched off the database (500 rows at
  a time) inside one transaction, so the full result set is never held in memory as Python
  objects. XLSX can't be streamed the same way — the `.xlsx` container is a zip archive
  that's only valid once fully written — so it's built with openpyxl's `write_only` mode
  (which still avoids holding a full worksheet object graph) into an in-memory buffer and
  returned as one chunk.
- **Filenames**: `expensa-expenses-YYYYMMDD.csv` / `.xlsx`, with the matching `Content-Type`
  and a `Content-Disposition: attachment` header.
- **Empty results**: a filter that matches nothing still returns `200` with a valid
  headers-only file, not a `500` or an empty body.

The frontend's export control (next to the expenses filter bar) always sends the currently
active filters and sort, so what downloads matches what's on screen — including the empty
case, which downloads a valid headers-only file rather than erroring.

### Required manual step: provider spend cap

**This is not something code can enforce** — quotas and rate limits protect against a single
runaway user, but a hard ceiling on total spend has to be configured directly with the
provider as the final backstop. Before exposing this app to real users:

1. Log into the OpenAI platform dashboard for the account tied to `OPENAI_API_KEY`.
2. Under the billing/usage-limits section, set a hard monthly spend limit.
3. Confirm billing alert emails are configured.

Do this for every environment (dev, staging, production) that has a real API key configured.

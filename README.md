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

### Required manual step: provider spend cap

**This is not something code can enforce** — quotas and rate limits protect against a single
runaway user, but a hard ceiling on total spend has to be configured directly with the
provider as the final backstop. Before exposing this app to real users:

1. Log into the OpenAI platform dashboard for the account tied to `OPENAI_API_KEY`.
2. Under the billing/usage-limits section, set a hard monthly spend limit.
3. Confirm billing alert emails are configured.

Do this for every environment (dev, staging, production) that has a real API key configured.

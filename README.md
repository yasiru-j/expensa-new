# Expensa

**AI-powered invoice & receipt extraction with a multi-user expense dashboard.**
Upload a receipt — a photo, scan, or PDF — and Expensa extracts the vendor, date, totals, tax, and line items into a searchable, per-user expense database, with a review-and-confirm step so a human always has the last word.

<!-- Add once available:
[Live demo](https://…)  ·  [Demo video](https://…)
-->

---

## Why this project

Most receipt-tracking dies from data-entry friction. Expensa turns "a photo of a receipt" into "a confirmed database row" in a few seconds, using a vision model for extraction while keeping the accounting-critical parts — validation, isolation, and cost control — firmly under application control.

It's built as a **real multi-tenant SaaS**, not a happy-path demo. The engineering effort went where it matters:

- **Proven tenant isolation, not assumed.** Postgres Row-Level Security is enforced with a dedicated non-owner database role (`expensa_app`) plus `FORCE ROW LEVEL SECURITY`, because table owners silently bypass RLS — so isolation is tested against the real database as the app's own role, at both the SQL layer and through the HTTP API.
- **Spending strangers' money is designed out.** Every request runs `auth → rate limit → quota → file validation` *before* the paid extraction call ever happens, proven by a test asserting a rejected request makes zero API calls. Quota is gated by an atomic increment (not a race-prone read-then-write); rate limiting uses an atomic Redis sliding window.
- **Validation over trust.** The model returns structured JSON, but arithmetic (`subtotal + tax ≈ total`), dates, and currency are all re-validated server-side; low-confidence or inconsistent extractions are flagged for human review rather than silently saved.
- **Real concurrency correctness.** Refresh-token rotation uses an in-flight-request guard on the client and a short server-side grace window, so concurrent refreshes (e.g. two open tabs) can't race each other into a logout — with regression tests to prove it.

Full product and engineering reasoning lives in the planning docs:
**[PRD](docs/PRD.md)** · **[Technical Design (TRD)](docs/TRD.md)** · **[Implementation Plan](docs/IMPLEMENTATION_PLAN.md)**

---

## Screenshots

<!-- Replace with real images once captured -->
| Dashboard | Review & confirm | Expenses |
|---|---|---|
| _dashboard.png_ | _review.png_ | _table.png_ |

---

## Architecture

```
        ┌──────────────────────────┐
        │       React SPA          │
        │   (Vite + TypeScript)    │
        └────────────┬─────────────┘
                     │ HTTPS · JWT (access in memory,
                     │         refresh in httpOnly cookie)
        ┌────────────▼─────────────┐
        │      FastAPI backend      │
        │  auth · guardrails ·      │
        │  extraction · validation  │
        └───┬─────────┬────────┬────┘
            │         │        │
   ┌────────▼──┐  ┌───▼───┐  ┌─▼──────────────┐
   │ Postgres  │  │ Redis │  │   OpenAI API   │
   │  + RLS    │  │ quota │  │ (vision model) │
   └───────────┘  │ rate  │  └────────────────┘
        ▲         │ limit │
        │         └───────┘
   ┌────┴─────┐
   │  MinIO   │   S3-compatible object storage
   │ (files)  │   (per-user prefixes, presigned URLs)
   └──────────┘

   Multi-page PDFs are processed by a Redis-backed worker that
   opens its own RLS-scoped DB session (sets app.user_id itself).
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite) + TypeScript + Tailwind CSS + Recharts |
| Backend | FastAPI (Python 3.12, async) |
| Auth | JWT (access + refresh), bcrypt, Google OAuth (Authlib) |
| Data | Postgres + Row-Level Security, SQLAlchemy 2.0, Alembic |
| Storage | S3-compatible (MinIO locally) |
| Async / limits | Redis (worker jobs, quotas, sliding-window rate limiting) |
| Extraction | OpenAI API (vision model, structured JSON output) |
| Tests | pytest (async), 165 tests against real Postgres/Redis/MinIO |

---

## Getting started (local)

### Prerequisites
- Docker + Docker Compose
- An OpenAI API key — **only needed to run a real extraction** (you can sign up, log in, and browse the app without one)

### 1. Configure environment
```bash
cp .env.example .env
```
Open `.env` and set values. For **local development you don't need any external accounts** — Postgres, Redis, and MinIO all run as containers and configure themselves from the values you choose. The only genuinely external variable is `OPENAI_API_KEY`, and only for receipt extraction. Google OAuth variables are optional (email/password login works without them).

### 2. Start the stack
```bash
docker compose up -d
```
This brings up five services: `postgres`, `redis`, `minio`, `backend`, `frontend`.

### 3. Open the app
- **Frontend:** http://localhost:5173
- **API:** http://localhost:8000

### 4. Create an account
Sign up in the browser. Email delivery is stubbed in local dev, so the verification link is written to the backend logs rather than emailed:
```bash
docker compose logs -f backend   # look for the logged verification link, open it
```
Or verify directly (the `expensa_owner` role bypasses RLS, which `expensa_app` intentionally cannot):
```bash
docker compose exec postgres psql -U expensa_owner -d expensa \
  -c "UPDATE users SET email_verified = true WHERE email = 'you@example.com';"
```
Then log in.

> To run a real extraction, put your real `OPENAI_API_KEY` in `.env` and restart the backend (`docker compose restart backend`).

---

## Running the tests

```bash
docker compose exec backend pytest        # backend suite (real Postgres/Redis/MinIO)
```
```bash
cd frontend && npm ci && npm run build && npm run lint
```

The suite includes cross-tenant isolation tests at both the database and HTTP layers, guardrail-ordering tests (a rejected upload makes zero OpenAI calls), quota/rate-limit concurrency tests, and the refresh-rotation regression tests.

---

## Project structure

```
expensa/
├── docs/                 # PRD, TRD, Implementation Plan
├── backend/              # FastAPI app, extraction, storage, Alembic, tests
│   └── app/
│       ├── api/          # routers: auth, expenses, dashboard, export, account
│       ├── core/         # config, security (JWT), dependencies, logging
│       ├── db/           # SQLAlchemy models, sessions, RLS helpers
│       ├── extraction/   # OpenAI client, schema, validation
│       └── worker.py     # async multi-page PDF processing
├── frontend/             # React (Vite + TS) SPA
├── docker-compose.yml
└── .env.example
```

---

## Security notes

- **Two-role Postgres + forced RLS:** migrations run as `expensa_owner`; the app connects as the non-owner `expensa_app`, so RLS policies actually apply. Isolation is enforced by the database, not just application code.
- **Secrets stay server-side:** the OpenAI key and DB credentials never reach the browser.
- **Tokens:** access token in memory, refresh token in an httpOnly/SameSite cookie; single-use rotation with a short reuse grace window and out-of-window rejection.
- **File uploads:** validated by magic bytes (not the client-declared content type), size-capped during read, stored under unguessable per-user keys and served via short-lived presigned URLs.
- **Exports:** CSV formula-injection is neutralized; currencies are never summed across each other.

---

## Deployment

Local dev uses containerized MinIO and default credentials. Before any public deployment:

- Replace every `changeme-*` secret and set a strong JWT secret.
- Swap MinIO for a managed S3-compatible store (AWS S3, Cloudflare R2, or similar).
- Set a hard spend cap in the OpenAI dashboard (this is an operational step, not code).
- Wire a real email provider (or ship a seeded demo account so reviewers skip signup).
- Set a real contact address on the Privacy/Terms pages.

---

## License

<!-- Choose one, e.g. MIT -->
_TBD_

---

<!--
Confirm against your docker-compose.yml before publishing:
- backend port (assumed 8000) and any exposed MinIO console port
- exact service names (assumed: postgres, redis, minio, backend, frontend)
- the authoritative env var list lives in .env.example — this README references it rather than duplicating it
- test command paths if your pytest invocation differs
-->

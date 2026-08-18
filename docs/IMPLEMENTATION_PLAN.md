# Implementation Plan — Expensa

> **How Expensa gets built: an ordered, phased plan from empty repo to shippable v1.**
> Companion to the PRD and TRD.

| | |
|---|---|
| **Document status** | Draft v1.1 |
| **Last updated** | August 2026 |
| **Owner** | *(your name)* |
| **Related docs** | PRD.md, TRD.md |

---

## 1. Guiding Principles

- **Ship a walkable slice early.** Each phase ends in something demonstrable, not half-built plumbing.
- **Security is not a phase.** RLS, server-side secrets, and per-user scoping are built in from the first data model, never retrofitted.
- **The AI is the easy part.** Extraction is one well-isolated module; most effort goes into auth, data isolation, review UX, and guardrails.
- **Validate, don't trust.** Every OpenAI response passes server-side (Pydantic + arithmetic) validation before it touches the database.
- **Cost control from day one of the extraction work**, not after the first surprise bill.

---

## 2. Tech Stack (locked)

| Layer | Choice |
|---|---|
| Frontend | React (Vite) + Tailwind CSS + Recharts |
| Backend | FastAPI (Python 3.12), async |
| Auth | JWT (access + refresh), bcrypt, Google OAuth via Authlib |
| ORM / migrations | SQLAlchemy 2.0 (async) + Alembic |
| Database | Postgres with Row-Level Security |
| Storage | S3-compatible object storage (MinIO locally) |
| Extraction | OpenAI API (vision model, structured JSON output) |
| Async jobs | Redis + worker (Celery or ARQ) |

---

## 3. Suggested Repository Structure

```
expensa/
├── docs/
│   ├── PRD.md
│   ├── TRD.md
│   └── IMPLEMENTATION_PLAN.md
├── backend/                     # FastAPI (Python)
│   ├── app/
│   │   ├── main.py              # app factory, router registration
│   │   ├── api/                 # routers: auth, expenses, dashboard, export
│   │   ├── core/                # config, security (JWT), dependencies
│   │   ├── db/                  # SQLAlchemy models, session, RLS helper
│   │   ├── extraction/          # OpenAI client, schema, validation
│   │   ├── usage/               # quota + rate limiting
│   │   └── workers/             # Celery/ARQ tasks (async PDF jobs)
│   ├── alembic/                 # versioned migrations
│   ├── tests/                   # pytest: unit, integration, security
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                    # React (Vite)
│   ├── src/
│   │   ├── pages/               # login, dashboard, upload, review
│   │   ├── components/
│   │   └── lib/                 # api client, auth/token handling
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml           # postgres + redis + minio + backend + frontend
├── .env.example                 # documented, no real secrets
└── README.md
```

---

## 4. Phase 0 — Project Setup

**Goal:** a running skeleton with tooling and secrets management in place.

**Tasks**
- Scaffold the FastAPI backend (`pyproject.toml`, app factory, health route) and the React (Vite) frontend.
- Add `docker-compose.yml` for local dev: Postgres, Redis, MinIO, backend, frontend.
- Initialize Alembic; wire an async SQLAlchemy engine/session.
- Configure linting/formatting: ruff + black (Python), ESLint + Prettier (JS).
- Add `.env.example` documenting every variable (DB URL, JWT secret, OpenAI key, S3 creds) — **no real values committed**.
- Set up CI to run lint + tests on push.
- Commit the three docs into `docs/`.

**Definition of Done**
- `docker-compose up` brings the whole stack online locally.
- Backend health check and an empty React page both load.
- CI passes; nothing sensitive is in source control.

---

## 5. Phase 1 — Foundation: Auth + Data Model + RLS

**Goal:** users can sign up and log in; the database enforces isolation from the very first table.

**Tasks**
- Define SQLAlchemy models for `users`, `expenses`, `line_items`, `usage`; generate the first Alembic migration (per the TRD DDL).
- Enable RLS on all user-owned tables; add the session-variable policies; add a DB dependency that runs `SET LOCAL app.user_id` per request transaction.
- Implement JWT auth in FastAPI: signup (bcrypt hashing + email verification), login (access + refresh), refresh rotation.
- Add Google OAuth via Authlib.
- Build a reusable `get_current_user` dependency used by every protected route.
- Build React auth pages (login, signup, reset) and token handling; add a protected-route wrapper and an empty dashboard shell.

**Definition of Done**
- A user can register, verify, log in, refresh, and log out.
- Unauthenticated requests to protected endpoints are rejected.
- A pytest test proves user A cannot read user B's rows (RLS holds even without an explicit `user_id` filter).

---

## 6. Phase 2 — Core Loop: Upload → Extract → Save → List

**Goal:** the central value of the product works end to end.

**Tasks**
- Build the React upload UI (drag-and-drop + mobile camera capture).
- Implement `POST /api/expenses/upload`: validate file type/size/page count, compute `file_hash`, store the original in the per-user MinIO/S3 prefix, create an `expenses` row with `status = processing`.
- Build the extraction module in `app/extraction/`:
  - Call the OpenAI vision model with the JSON schema and temperature ≈ 0.
  - Parse the response into a Pydantic model.
- Add the validation layer: arithmetic check (`subtotal + tax ≈ total`), date/currency normalization, non-receipt rejection.
- Persist validated data; set `status = ready`.
- Build the React expenses table (list, sort by date).

**Definition of Done**
- Uploading a sample receipt produces a saved, validated expense visible in the table.
- A non-receipt image is rejected gracefully (no fabricated data).
- A malformed OpenAI response retries once, then fails cleanly with a clear status.

---

## 7. Phase 3 — Review & Confirm UX

**Goal:** humans correct the AI before anything becomes final.

**Tasks**
- Build the React review screen: extracted fields in an editable form beside the original document image (served via presigned URL).
- Highlight low-confidence and validation-flagged fields.
- Implement `PATCH /api/expenses/{id}` to save corrections and `POST /api/expenses/{id}/confirm` to finalize.
- Track which fields were AI-extracted vs. user-corrected (feeds the accuracy metric).

**Definition of Done**
- A user can open a `ready` expense, edit any field, and confirm it.
- Only `confirmed` expenses are treated as final in the dashboard.
- Low-confidence fields are visually flagged for attention.

---

## 8. Phase 4 — Insights: Dashboard & Search

**Goal:** users understand their spending at a glance.

**Tasks**
- Implement `GET /api/dashboard/summary`: monthly total, spend by category, receipt count (SQL aggregation, owner-scoped).
- Build React summary cards and Recharts visuals (spend-over-time line, spend-by-category breakdown).
- Add search and filters to the expenses table: date range, category, free-text vendor search, pagination.

**Definition of Done**
- Dashboard reflects only the logged-in user's confirmed expenses.
- Filters and search return correct, owner-scoped results.
- Charts update as data changes.

---

## 9. Phase 5 — Guardrails: Quotas, Rate Limits, Cost Control

**Goal:** the app is safe to expose to strangers without risking runaway cost.

**Tasks**
- Enforce per-user monthly quota via the `usage` table; block and message clearly when exceeded.
- Add Redis-backed per-user rate limiting (sliding window) on the upload endpoint.
- Enforce file size and page-count caps *before* any OpenAI call.
- Use `file_hash` for idempotency to avoid re-charging for duplicate uploads.
- Implement OpenAI model tiering: cheap model first, escalate on low confidence/failure.
- Configure a hard spend cap in the OpenAI dashboard as a final backstop.
- Surface current usage on the account page (`GET /api/usage`).

**Definition of Done**
- Exceeding the quota blocks extraction with a helpful message.
- Rapid repeated uploads are throttled.
- Guardrail checks run before the paid API call, in order (auth → rate limit → quota → file check → extract).

---

## 10. Phase 6 — Export

**Goal:** data leaves the app cleanly for accounting workflows.

**Tasks**
- Implement `GET /api/export` to stream CSV and Excel of the currently filtered results (e.g. pandas/openpyxl or a streaming CSV writer).
- Ensure exports respect active filters and are owner-scoped.

**Definition of Done**
- A user can export their filtered expenses to CSV and Excel.
- Exported totals match the dashboard.

---

## 11. Phase 7 — Polish & Hardening

**Goal:** the rough edges that separate a demo from a product.

**Tasks**
- Empty states, loading states, and clear error messaging throughout.
- Duplicate detection surfacing (same vendor + date + amount).
- Account deletion: hard-delete rows and stored files (`DELETE /api/account`).
- Privacy policy and terms pages.
- Async processing for multi-page PDFs via the Redis worker, with status polling.
- Accessibility pass and mobile-responsiveness check.
- Observability: structured logs and key metrics (success rate, latency, cost/extraction).

**Definition of Done**
- Full happy path is smooth on desktop and mobile.
- Account deletion removes all traces of a user.
- Multi-page PDFs process without blocking the UI.

---

## 12. Testing Checkpoints (run continuously)

| From phase | Tests added |
|---|---|
| 1 | RLS cross-tenant isolation test; JWT/auth dependency tests. |
| 2 | Extraction validation unit tests; upload → save integration test (mocked OpenAI). |
| 3 | Review edit/confirm flow test. |
| 4 | Dashboard aggregation correctness; owner-scoping on filters. |
| 5 | Quota math; rate-limit behavior; idempotency. |
| 7 | End-to-end happy path; account-deletion completeness. |

---

## 13. Milestones (demo-able states)

1. **M1 — "I can log in."** (end of Phase 1)
2. **M2 — "I uploaded a receipt and it appeared as data."** (end of Phase 2)
3. **M3 — "I corrected and confirmed it."** (end of Phase 3)
4. **M4 — "I can see my spending dashboard."** (end of Phase 4)
5. **M5 — "It's safe for real users."** (end of Phase 5)
6. **M6 — "It's a product."** (end of Phase 7)

Each milestone is a natural point to record a short demo clip or screenshot for the portfolio.

---

## 14. Definition of Done — v1

- Multi-user JWT auth with verified accounts and full per-user data isolation (RLS-backed).
- Reliable upload → OpenAI extraction → validation → review → confirm loop.
- Dashboard with summaries, search, and filters.
- Quotas, rate limits, file caps, idempotency, and a provider spend cap all active.
- CSV/Excel export.
- Account deletion, privacy/terms pages, and basic observability.
- Test suite covering isolation, validation, and the end-to-end happy path.

---

## 15. Risk Checkpoints

| Checkpoint | Question to answer before moving on |
|---|---|
| After Phase 1 | Can any user reach another user's data by any path? (Must be no.) |
| After Phase 2 | Does validation actually catch bad extractions, or is bad data slipping through? |
| After Phase 5 | Could a single abusive user run up the OpenAI bill? (Must be no.) |
| Before launch | Is the average cost per extraction within the intended budget? |

---

*End of document.*

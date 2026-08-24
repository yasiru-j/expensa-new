# Technical Requirements Document — Expensa

> **Technical design for an AI-powered invoice & receipt extraction platform with a multi-user expense dashboard.**
> Companion to the Product Requirements Document (PRD).

| | |
|---|---|
| **Document status** | Draft v1.1 |
| **Last updated** | August 2026 |
| **Owner** | *(your name)* |
| **Related docs** | PRD.md, IMPLEMENTATION_PLAN.md |

---

## 1. Purpose & Scope

This document translates the product requirements into a concrete technical design. It covers the system architecture, data model, extraction pipeline, API contracts, security model, and operational concerns for **Expensa v1**.

Out of scope for this document: accounting integrations, team workspaces, and billing — noted as future phases in the PRD, each to get its own design when prioritized.

---

## 2. Architecture Overview

Expensa is a **React single-page application** talking to a **FastAPI (Python) backend**. The backend owns authentication, orchestrates extraction via the OpenAI API, and persists data to Postgres with row-level security. Source files live in private object storage.

```
                        ┌────────────────────────────┐
                        │          Client             │
                        │   React SPA (Vite) + JWT    │
                        └─────────────┬───────────────┘
                                      │ HTTPS  (Bearer token)
                        ┌─────────────▼───────────────┐
                        │       FastAPI Backend        │
                        │  - JWT auth guard            │
                        │  - rate limit / quota check  │
                        │  - extraction orchestration  │
                        │  - validation                │
                        └───┬───────────┬─────────┬───┘
                            │           │         │
              ┌─────────────▼──┐  ┌─────▼─────┐ ┌─▼──────────────┐
              │   Postgres     │  │  Object   │ │   OpenAI API   │
              │   + RLS        │  │  Storage  │ │ (vision model) │
              └────────────────┘  └───────────┘ └────────────────┘
                            ▲
                    ┌───────┴────────┐
                    │ Redis + worker │  (async multi-page PDF jobs)
                    └────────────────┘
```

**Key rule:** the OpenAI API key and DB credentials exist only in server-side environment variables on the FastAPI backend. No secret ever reaches the browser. Every data-access path is guarded twice — once by the API's JWT auth dependency, and again by Postgres RLS as defense in depth.

---

## 3. Technology Choices & Rationale

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | **React (Vite)** + Tailwind CSS + Recharts | Fast SPA build, polished dashboard UI, strong ecosystem. |
| Backend | **FastAPI** (Python 3.12), async | Modern, typed, async I/O suits OpenAI + DB calls; Pydantic gives typed contracts. |
| Auth | **JWT** (access + refresh), bcrypt hashing, Authlib for Google OAuth | Self-contained, demonstrates real backend security work. |
| ORM / migrations | **SQLAlchemy 2.0** (async) + **Alembic** | Typed models, versioned schema changes. |
| Database | **Postgres** with Row-Level Security | Relational data, transactions, DB-enforced isolation. |
| Storage | S3-compatible object storage (MinIO locally) | Private buckets, per-user prefixes, presigned URLs. |
| Extraction | **OpenAI API** — vision model (e.g. GPT-4o / GPT-4o-mini) | Handles messy scans without brittle templates; native structured JSON output. |
| Async jobs | **Redis** + worker (Celery or ARQ) | Non-blocking processing for multi-page PDFs. |
| Rate limiting | Redis-backed sliding window (e.g. slowapi) | Per-user upload throttling. |

> Decisions are recorded here rather than left implicit so the trade-offs are auditable.

---

## 4. Data Model

### 4.1 Schema (DDL)

```sql
create extension if not exists citext;      -- case-insensitive email

-- Users: owned by the API (JWT auth)
create table users (
  id             uuid primary key default gen_random_uuid(),
  email          citext unique not null,
  password_hash  text,                       -- null for OAuth-only accounts
  email_verified boolean not null default false,
  created_at     timestamptz not null default now()
);

-- Expenses: one row per confirmed or in-progress document
create table expenses (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid not null references users(id) on delete cascade,
  vendor             text,
  vendor_tax_id      text,
  expense_date       date,
  subtotal           numeric(12,2),
  tax                numeric(12,2),
  total              numeric(12,2),
  currency           char(3) default 'AUD',
  category           text,
  payment_method     text,
  status             text not null default 'pending'
                     check (status in ('pending','processing','ready','confirmed','failed')),
  file_url           text,
  file_hash          text,                    -- for idempotency / dedupe
  extracted_confidence numeric(4,3),          -- 0.000–1.000
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

-- Line items: many per expense
create table line_items (
  id           uuid primary key default gen_random_uuid(),
  expense_id   uuid not null references expenses(id) on delete cascade,
  description  text,
  quantity     numeric(12,3),
  unit_price   numeric(12,2),
  amount       numeric(12,2)
);

-- Usage: per-user monthly extraction counter for quotas
create table usage (
  user_id          uuid not null references users(id) on delete cascade,
  period_month     date not null,            -- first day of month
  extraction_count int  not null default 0,
  primary key (user_id, period_month)
);

-- Helpful indexes
create index idx_expenses_user_date on expenses (user_id, expense_date desc);
create index idx_expenses_user_status on expenses (user_id, status);
create index idx_expenses_user_hash on expenses (user_id, file_hash);
create index idx_line_items_expense on line_items (expense_id);
```

### 4.2 Row-Level Security

RLS is the backbone of tenant isolation. Because the API owns auth (rather than a managed provider), the backend sets the current user id as a **per-transaction Postgres session variable**, and RLS policies read it. This keeps isolation enforced at the database layer even if an application query forgets its `user_id` filter.

```sql
alter table expenses   enable row level security;
alter table line_items enable row level security;
alter table usage      enable row level security;

-- FORCE so RLS also applies to the table owner (the migration role) — without
-- it, only non-owner roles are restricted. The app connects as a separate,
-- non-owner, non-superuser role (expensa_app) for exactly this reason.
alter table expenses   force row level security;
alter table line_items force row level security;
alter table usage      force row level security;

-- NULLIF(..., '') guards a real Postgres/pooling gotcha: once a session has
-- set a custom GUC at least once, current_setting(..., true) on a later
-- transaction over the same pooled connection can return '' — not NULL — if
-- the variable wasn't set again. '' would otherwise fail the ::uuid cast
-- instead of comparing (correctly) as not-equal.

-- Expenses: owner-only, keyed off the request's session variable
create policy expenses_isolation on expenses
  for all
  using      (user_id = nullif(current_setting('app.user_id', true), '')::uuid)
  with check (user_id = nullif(current_setting('app.user_id', true), '')::uuid);

-- Line items: access via parent expense ownership
create policy line_items_isolation on line_items
  for all
  using (
    exists (select 1 from expenses e
            where e.id = line_items.expense_id
              and e.user_id = nullif(current_setting('app.user_id', true), '')::uuid)
  )
  with check (
    exists (select 1 from expenses e
            where e.id = line_items.expense_id
              and e.user_id = nullif(current_setting('app.user_id', true), '')::uuid)
  );

-- Usage: owner-only
create policy usage_isolation on usage
  for all
  using      (user_id = nullif(current_setting('app.user_id', true), '')::uuid)
  with check (user_id = nullif(current_setting('app.user_id', true), '')::uuid);
```

**Setting the variable per request (FastAPI + SQLAlchemy):**

```python
# Inside a per-request DB transaction, after authenticating the user:
await session.execute(
    text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(current_user.id)}
)
```

`set_config(name, value, is_local=true)` is `SET LOCAL` expressed as a function call rather than
the `SET LOCAL` statement itself — the statement's own grammar takes a string literal for the
value, not a bind parameter, so it can't be used safely with parameterized queries. The function
form accepts a normal bind parameter and has identical transaction-local scoping: the value resets
at the end of the transaction, so it never leaks across requests on a pooled connection.

**Storage:** source files are stored under a per-user path prefix (e.g. `receipts/{user_id}/{expense_id}.{ext}`) in a private bucket, served via short-lived **presigned URLs** — never public links.

---

## 5. Extraction Pipeline

The pipeline is the technical heart of Expensa. It is designed to be deterministic in structure (fixed output schema) even though the model itself is probabilistic.

### 5.1 Flow

```
Upload → Validate file → Store original → (enqueue if multi-page)
      → Call OpenAI vision model with schema → Parse JSON
      → Arithmetic + date validation → Persist as `ready`
      → User reviews/edits → `confirmed`
```

### 5.2 OpenAI integration

- **SDK & endpoint:** the official OpenAI Python SDK, Chat Completions with an image input (base64 data URL), called from FastAPI with the secret key.
- **Structured output:** the request uses a strict JSON schema response format so the model returns valid JSON — no brittle text parsing. The result is parsed into a Pydantic model.
- **Model tiering (cost lever):** default to a **cheaper vision model** (e.g. GPT-4o-mini class) for standard receipts; **escalate to a larger model** (e.g. GPT-4o class) only when the first pass returns low confidence or fails validation. Keeps average cost low while preserving accuracy on hard cases.
- **Determinism:** temperature near 0 for stable, repeatable extractions.
- **Token/cost guards:** images are downscaled to a sensible max dimension before upload to cut token cost without hurting legibility.

```python
# Illustrative — the extraction call (server-side only)
from openai import OpenAI
client = OpenAI()

resp = client.chat.completions.create(
    model="gpt-4o-mini",
    temperature=0,
    response_format={"type": "json_schema", "json_schema": RECEIPT_SCHEMA},
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": EXTRACTION_PROMPT},
            {"type": "image_url",
             "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        ],
    }],
)
data = ReceiptExtraction.model_validate_json(resp.choices[0].message.content)
```

### 5.3 Extraction contract

The model returns **only** JSON matching a fixed schema (enforced by a Pydantic model server-side), with nulls for missing fields and an explicit non-receipt signal.

```json
{
  "is_receipt": true,
  "vendor": "string | null",
  "vendor_tax_id": "string | null",
  "date": "YYYY-MM-DD | null",
  "currency": "ISO 4217 | null",
  "subtotal": "number | null",
  "tax": "number | null",
  "total": "number | null",
  "payment_method": "string | null",
  "category": "one of a fixed enum | null",
  "line_items": [
    { "description": "string", "quantity": "number | null",
      "unit_price": "number | null", "amount": "number | null" }
  ],
  "confidence": "number 0-1"
}
```

**Category enum (fixed):** `Meals`, `Travel`, `Office Supplies`, `Software`, `Utilities`, `Professional Services`, `Other`.

### 5.4 Design safeguards
- **Structured output:** parsed into a Pydantic model; a parse/validation failure triggers one retry, then a `failed` status with a clear message.
- **Non-receipt handling:** if `is_receipt` is false, the document is rejected without fabricating fields.
- **Validation layer (server-side, not the model's job):**
  - `subtotal + tax ≈ total` within a small rounding tolerance; mismatch lowers effective confidence and flags for review.
  - Dates normalized to ISO; unparseable dates are nulled and flagged.
  - Currency normalized to ISO 4217; defaults to the user's locale currency if absent.
- **Confidence flagging:** extractions below a threshold are surfaced prominently in the review UI.

### 5.5 Async processing
Single-page images are processed inline in the request. Multi-page PDFs are dispatched to a **Redis-backed worker** (Celery/ARQ) so requests never block; the client polls expense status until `processing → ready`.

---

## 6. API Design

FastAPI routers expose a JSON API. Every route depends on a JWT auth dependency that resolves the current user; the API never trusts a client-supplied user identifier.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/auth/signup` | Register; send verification email. |
| `POST` | `/api/auth/login` | Issue access + refresh tokens. |
| `POST` | `/api/auth/refresh` | Rotate access token. |
| `GET`  | `/api/auth/google` | Google OAuth entry (Authlib). |
| `POST` | `/api/expenses/upload` | Accept file, validate, store, run/enqueue extraction. Returns `id` + `status`. |
| `GET`  | `/api/expenses/{id}` | Fetch a single expense (owner-scoped). |
| `PATCH`| `/api/expenses/{id}` | Save user corrections during review. |
| `POST` | `/api/expenses/{id}/confirm` | Mark as `confirmed`. |
| `GET`  | `/api/expenses` | List with filters: `date_from`, `date_to`, `category`, `q`, `sort`, pagination. |
| `DELETE`| `/api/expenses/{id}` | Delete expense + file. |
| `GET`  | `/api/dashboard/summary` | Aggregates: monthly total, by-category, count. |
| `GET`  | `/api/export` | Stream CSV/Excel of filtered results. |
| `GET`  | `/api/usage` | Current-period quota consumption. |
| `DELETE`| `/api/account` | Hard-delete account, rows, and files. |

**Upload guardrails** run *before* any OpenAI call, in order: JWT auth → rate-limit check → quota check → file-type/size/page-count check → **then** extraction.

---

## 7. Security Design

- **Secret handling:** OpenAI API key and DB credentials live only in server-side env vars on the FastAPI backend; never bundled to the client.
- **Auth:** JWT access + refresh tokens; bcrypt password hashing; email verification; Google OAuth via Authlib; tokens carry minimal claims and short access-token lifetimes.
- **Tenant isolation:** enforced at two layers — FastAPI auth dependency (application) + Postgres RLS via per-transaction session variable (database).
- **Transport & storage:** TLS in transit; encryption at rest for DB and files; private buckets with presigned URLs.
- **Input hardening:** strict MIME/type validation; size and page caps; reject executables and oversized payloads early; Pydantic validation on all request bodies.
- **Data lifecycle:** account deletion cascades to expenses, line items, usage, and stored files.
- **Compliance basics:** privacy policy and terms pages; documented data-retention behavior.

---

## 8. Cost Control & Abuse Prevention

Because extraction has a real per-call cost and the app is multi-user, cost control is a technical requirement, not an afterthought.

| Control | Mechanism |
|---|---|
| **Quota** | `usage` table; increment per extraction; block when monthly cap reached. |
| **Rate limit** | Redis-backed per-user sliding window (e.g. 20 uploads/hour) at the API layer. |
| **File caps** | Reject oversized files and excessive page counts before the OpenAI call. |
| **Provider cap** | Hard monthly usage/spend limit configured in the OpenAI dashboard as a final backstop. |
| **Idempotency** | Deduplicate repeat uploads via `file_hash` to avoid double-charging. |
| **Model tiering** | Cheap model first; escalate only on low confidence/failure. |

---

## 9. Observability & Operations

- **Logging:** structured logs for uploads, extraction latency, validation failures, and quota hits (no sensitive financial values in logs).
- **Metrics:** extraction success rate, median latency, cost per extraction, quota-block rate.
- **Error tracking:** capture and alert on extraction and API failures.
- **Backups:** daily automated Postgres backups; documented restore procedure.

---

## 10. Testing Strategy

| Level | Coverage |
|---|---|
| **Unit** | Validation logic (arithmetic tolerance, date/currency normalization), quota math, JWT/auth helpers. |
| **Integration** | Upload → extraction (mocked OpenAI) → persist → retrieve, with RLS enforced. |
| **Security** | Cross-tenant access attempts must fail (user A cannot read user B's rows/files). |
| **E2E** | Happy path: sign up → upload → review → confirm → dashboard → export. |
| **Fixtures** | Sample receipts (clean, skewed, multi-page, non-receipt) for regression. |

Tooling: **pytest** (+ httpx async client) on the backend; a component/e2e runner on the React side.

---

## 11. Deployment & Environments

- **Containerized:** Dockerfiles for backend and frontend; `docker-compose` for local dev (Postgres + Redis + backend + frontend + MinIO).
- **Environments:** local → staging → production, with separate databases and buckets.
- **Hosting:** FastAPI backend on a container host; React SPA served as static assets/CDN; managed Postgres and Redis.
- **CI/CD:** on push, run lint (ruff/black, ESLint) + tests; deploy on merge to main.
- **Migrations:** schema changes applied via Alembic revisions.
- **Secrets:** injected via environment configuration; `.env.example` documents required vars with no real values.

---

## 12. Open Technical Decisions

- Worker choice: **Celery vs. ARQ** for background jobs (ARQ is lighter and async-native; Celery is more battle-tested).
- Inline vs. always-async extraction (start inline for single-page, async for PDFs — revisit if latency degrades).
- Session-variable RLS vs. purely application-layer scoping (plan keeps both as defense in depth).
- Export generation on-the-fly vs. pre-built (start on-the-fly).

---

*End of document.*

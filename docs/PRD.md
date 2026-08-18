# Product Requirements Document — ReceiptIQ

> **AI-powered invoice & receipt extraction with a multi-user expense dashboard.**
> *(ReceiptIQ is a working name — rename freely.)*

| | |
|---|---|
| **Document status** | Draft v1.0 |
| **Last updated** | August 2026 |
| **Owner** | *(your name)* |
| **Type** | Full-stack SaaS side project |

---

## 1. Overview

ReceiptIQ lets a user upload an invoice or receipt — a PDF, a scan, or a phone photo — and automatically extracts the structured financial data (vendor, date, totals, tax, line items) into a searchable expense database. Each user has their own account and dashboard showing spending trends, category breakdowns, and exportable reports.

The problem it solves: manually typing receipts into a spreadsheet is slow, error-prone, and nobody keeps it up to date. Small businesses, freelancers, and individuals lose track of deductible expenses because the friction of data entry is too high. ReceiptIQ reduces "photo of a receipt" to "a confirmed database row" in a few seconds.

This document defines the scope, requirements, architecture, and delivery plan for v1.

---

## 2. Goals & Non-Goals

### Goals
- Extract key fields from a receipt/invoice image or PDF with high accuracy, including messy or low-quality scans.
- Provide secure multi-user accounts where each user's financial data is fully isolated from others.
- Offer a dashboard with spending summaries, category breakdowns, and search/filter.
- Let users review and correct extracted data before it's committed (human-in-the-loop).
- Support CSV/Excel export for accounting workflows.

### Non-Goals (v1)
- Full double-entry accounting or general ledger.
- Direct integrations with accounting platforms (Xero, QuickBooks) — deferred to a later phase.
- Team/organization shared workspaces — v1 is per-individual.
- Mobile native apps — the web app will be mobile-responsive instead.
- Automated tax filing or compliance guarantees.

---

## 3. Target Users

| Persona | Need |
|---|---|
| **Freelancer / sole trader** | Track deductible business expenses without manual entry. |
| **Small business owner** | Keep receipts organized for bookkeeping and tax time. |
| **Budget-conscious individual** | Understand where money goes across categories. |

---

## 4. User Stories

- As a **new user**, I can sign up with email or Google so I can start quickly.
- As a **user**, I can upload a receipt image or PDF so it gets processed automatically.
- As a **user**, I can review the extracted fields and correct any mistakes before saving.
- As a **user**, I can see all my expenses in a searchable, filterable table.
- As a **user**, I can view a dashboard with monthly totals and category breakdowns.
- As a **user**, I can export my expenses to CSV/Excel for my accountant.
- As a **user**, I can only ever see my own data — never anyone else's.
- As a **user**, I can delete my account and all associated data.

---

## 5. Functional Requirements

### 5.1 Authentication
- Email/password sign-up with email verification.
- Google OAuth sign-in.
- Password reset flow.
- Session management with secure, http-only tokens.

### 5.2 Upload & Ingestion
- Accept JPG, PNG, and PDF files.
- Enforce a max file size (e.g. 10 MB) and page limit before processing.
- Store the original file in per-user storage; never discard the source document.
- Show upload progress and processing status (`pending → processing → ready → confirmed`).

### 5.3 Extraction
- Send the document to a vision-capable LLM API and receive structured JSON.
- Target fields: `vendor`, `vendor_tax_id` (e.g. ABN), `date`, `subtotal`, `tax`, `total`, `currency`, `payment_method`, `category`, and `line_items[]`.
- Auto-categorize into a fixed taxonomy (e.g. Meals, Travel, Office Supplies, Software, Utilities, Other).
- Return a confidence signal; low-confidence extractions are flagged for review.
- Gracefully handle non-receipt images by returning an error state rather than fabricated data.

### 5.4 Validation
- Verify arithmetic: `subtotal + tax ≈ total` (within rounding tolerance).
- Validate and normalize dates to ISO format.
- Normalize currency codes.
- Flag rows that fail validation for manual review.

### 5.5 Review & Confirm
- Present extracted fields in an editable form beside the original document image.
- User edits, then confirms — only confirmed rows count as final.
- Track which fields were AI-extracted vs. user-corrected (useful for measuring accuracy).

### 5.6 Dashboard & Search
- Summary cards: total spend this month, spend by category, receipt count.
- Charts: spend over time (line), spend by category (bar/pie).
- Expense table with search, date-range filter, category filter, and sort.

### 5.7 Export
- Export filtered results to CSV and Excel.

### 5.8 Account Management
- View usage against quota.
- Delete account: hard-deletes all rows and stored files.

---

## 6. Technical Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Browser   │────▶│   FastAPI API    │────▶│   OpenAI API    │
│ (React SPA) │     │   (Python)       │     │ (vision model)  │
└─────────────┘     └────────┬─────────┘     └─────────────────┘
                             │
                   ┌─────────┴─────────┐
                   │                   │
             ┌─────▼─────┐      ┌──────▼──────┐
             │ Postgres  │      │ File Storage│
             │ (w/ RLS)  │      │ (per-user)  │
             └───────────┘      └─────────────┘
```

### Proposed stack
- **Frontend:** React (Vite) single-page app + Tailwind CSS + Recharts, mobile-responsive.
- **Backend:** FastAPI (Python), async, serving a JSON API to the React client.
- **Auth:** JWT-based authentication owned by the API (password hashing + Google OAuth).
- **Database:** Postgres via SQLAlchemy, with schema migrations managed by Alembic.
- **Storage:** private object storage (S3-compatible) with per-user key prefixes.
- **Extraction:** the **OpenAI API** (a vision-capable model), called **server-side only** from FastAPI.

### Critical security principle
The OpenAI API key and all extraction calls live **exclusively on the server** (the FastAPI backend). The frontend never touches the key. Every database query is scoped to the authenticated user via Postgres **Row-Level Security (RLS)** — data isolation is enforced at the database layer, not just in application code.

---

## 7. Data Model

```
users            (owned by the API — JWT auth)
  id, email, password_hash, email_verified, created_at

expenses
  id, user_id (FK), vendor, vendor_tax_id, date,
  subtotal, tax, total, currency, category,
  payment_method, status, file_url,
  extracted_confidence, created_at, updated_at

line_items
  id, expense_id (FK), description, quantity,
  unit_price, amount

usage
  user_id (FK), period_month, extraction_count
```

**RLS policy (conceptual):** every `SELECT / INSERT / UPDATE / DELETE` on `expenses`, `line_items`, and `usage` is permitted only where `user_id` matches the current request's authenticated user (set per-transaction as a Postgres session variable). Object storage uses per-user key prefixes with matching access rules.

---

## 8. Non-Functional Requirements

### Security & Privacy
- Full per-user data isolation via RLS.
- Files stored in private buckets with signed, time-limited URLs.
- Financial data encrypted at rest and in transit.
- Privacy policy and terms of service pages.
- Account and data deletion honored completely.

### Cost Control (critical for a shared, API-backed app)
- **Per-user quota** (e.g. free tier: 50 extractions/month), tracked in `usage`.
- **Rate limiting** (e.g. max 20 uploads/hour/user).
- **File guards** — size and page-count caps before any API call.
- **Hard spending cap** configured on the LLM provider account as a final safety net.

### Performance
- Extraction result returned within a few seconds for a single-page document.
- Async processing with status updates for multi-page PDFs.

### Reliability
- Failed extractions retry once, then surface a clear error.
- Daily database backups.

---

## 9. Success Metrics
- **Extraction accuracy:** % of fields requiring no user correction (target > 90% on clean documents).
- **Time-to-confirm:** median seconds from upload to confirmed row.
- **Activation:** % of new users who process at least one receipt.
- **Cost per extraction:** average API spend per processed document.

---

## 10. Delivery Roadmap

| Phase | Scope |
|---|---|
| **1. Foundation** | Auth, empty dashboard, database + RLS setup. |
| **2. Core loop** | Upload → extraction → validation → save → table view. |
| **3. Review UX** | Editable review/confirm screen beside source document. |
| **4. Insights** | Dashboard charts, category filters, search. |
| **5. Guardrails** | Quotas, rate limits, file guards. |
| **6. Export** | CSV/Excel export. |
| **7. Polish** | Duplicate detection, email-to-inbox ingestion, empty/error states. |

---

## 11. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Runaway API costs from heavy/abusive use | Quotas, rate limits, file caps, provider spending cap. |
| Extraction errors on poor-quality scans | Human-in-the-loop review before commit; confidence flags. |
| Sensitive financial data exposure | RLS, private storage, encryption, strict server-side key handling. |
| Users uploading non-receipts | Extraction returns an explicit error state, never fabricated data. |
| Multi-page / multi-receipt edge cases | Page-count limits; async processing; per-document splitting later. |

---

## 12. Future Enhancements (Post-v1)
- Accounting integrations (Xero, QuickBooks).
- Team/organization shared workspaces with roles.
- Email forwarding: send receipts to a dedicated inbox for auto-processing.
- Natural-language querying ("how much on software last quarter?").
- Duplicate detection (same vendor + date + amount).
- Recurring-expense detection and subscription tracking.
- Paid tiers with billing.

---

*End of document.*

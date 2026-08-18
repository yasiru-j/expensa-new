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
- The OpenAI API key and all extraction calls (Phase 2+) will run server-side only.

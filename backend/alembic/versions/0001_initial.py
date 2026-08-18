"""initial schema: users, expenses, line_items, usage + RLS + expensa_app role

Revision ID: 0001
Revises:
Create Date: 2026-08-19
"""

import os

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import CITEXT, UUID

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

APP_ROLE = "expensa_app"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "users",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("email", CITEXT(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "expenses",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vendor", sa.Text(), nullable=True),
        sa.Column("vendor_tax_id", sa.Text(), nullable=True),
        sa.Column("expense_date", sa.Date(), nullable=True),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=True),
        sa.Column("tax", sa.Numeric(12, 2), nullable=True),
        sa.Column("total", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=True, server_default="AUD"),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("payment_method", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("file_url", sa.Text(), nullable=True),
        sa.Column("file_hash", sa.Text(), nullable=True),
        sa.Column("extracted_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status in ('pending','processing','ready','confirmed','failed')",
            name="expenses_status_check",
        ),
    )

    op.create_table(
        "line_items",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "expense_id",
            UUID(as_uuid=True),
            sa.ForeignKey("expenses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=True),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
    )

    op.create_table(
        "usage",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("period_month", sa.Date(), primary_key=True, nullable=False),
        sa.Column("extraction_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_index("idx_expenses_user_date", "expenses", ["user_id", sa.text("expense_date desc")])
    op.create_index("idx_expenses_user_status", "expenses", ["user_id", "status"])
    op.create_index("idx_expenses_user_hash", "expenses", ["user_id", "file_hash"])
    op.create_index("idx_line_items_expense", "line_items", ["expense_id"])

    # --- Row-Level Security (TRD 4.2) ---
    for table in ("expenses", "line_items", "usage"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # FORCE is required so RLS also applies to the table owner (the
        # migration role) — without it, only non-owner roles are restricted.
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # NULLIF(..., '') guards a real Postgres/pooling gotcha: once a session
    # has SET LOCAL'd a custom GUC at least once, current_setting(..., true)
    # on a later transaction over the same pooled connection can return '' —
    # not NULL — if the variable wasn't set again. '' would otherwise fail
    # the ::uuid cast instead of comparing (correctly) as not-equal.
    op.execute("""
        CREATE POLICY expenses_isolation ON expenses
          FOR ALL
          USING      (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
          WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
        """)
    op.execute("""
        CREATE POLICY line_items_isolation ON line_items
          FOR ALL
          USING (
            EXISTS (SELECT 1 FROM expenses e
                    WHERE e.id = line_items.expense_id
                      AND e.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
          )
          WITH CHECK (
            EXISTS (SELECT 1 FROM expenses e
                    WHERE e.id = line_items.expense_id
                      AND e.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
          )
        """)
    op.execute("""
        CREATE POLICY usage_isolation ON usage
          FOR ALL
          USING      (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
          WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
        """)

    # --- expensa_app: restricted runtime role the API connects as ---
    # A non-owner, non-superuser role is required for RLS to mean anything —
    # table owners and superusers bypass RLS regardless of FORCE.
    app_password = os.environ.get("POSTGRES_APP_PASSWORD")
    if not app_password:
        raise RuntimeError(
            "POSTGRES_APP_PASSWORD must be set before running this migration "
            "(it provisions the restricted expensa_app role)."
        )
    # PASSWORD takes a string literal in Postgres's grammar, not a bind
    # parameter, so this value is inlined after manual escaping. It comes
    # from trusted deploy-time environment config, not user input.
    password_literal = app_password.replace("'", "''")

    connection = op.get_bind()
    role_exists = connection.execute(
        sa.text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": APP_ROLE}
    ).scalar()

    if role_exists:
        op.execute(f"ALTER ROLE {APP_ROLE} WITH LOGIN PASSWORD '{password_literal}'")
    else:
        op.execute(
            f"CREATE ROLE {APP_ROLE} WITH LOGIN PASSWORD '{password_literal}' "
            "NOSUPERUSER NOCREATEDB NOCREATEROLE"
        )

    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}"
    )


def downgrade() -> None:
    op.execute(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}")
    op.execute(f"DROP ROLE IF EXISTS {APP_ROLE}")

    op.execute("DROP POLICY IF EXISTS usage_isolation ON usage")
    op.execute("DROP POLICY IF EXISTS line_items_isolation ON line_items")
    op.execute("DROP POLICY IF EXISTS expenses_isolation ON expenses")

    op.drop_index("idx_line_items_expense", table_name="line_items")
    op.drop_index("idx_expenses_user_hash", table_name="expenses")
    op.drop_index("idx_expenses_user_status", table_name="expenses")
    op.drop_index("idx_expenses_user_date", table_name="expenses")

    op.drop_table("usage")
    op.drop_table("line_items")
    op.drop_table("expenses")
    op.drop_table("users")

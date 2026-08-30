"""add users.full_name

Optional (nullable) — collected at signup but never required, and editable
anytime from the account page. No RLS/GRANT changes needed: expensa_app
already has UPDATE on all tables (migration 0001), and the users table has
no RLS policy of its own — every write to it goes through
app.core.deps.get_current_user first, so the app layer (not the database)
is what scopes an update to the caller's own row. See app/api/account.py.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-30
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "full_name")

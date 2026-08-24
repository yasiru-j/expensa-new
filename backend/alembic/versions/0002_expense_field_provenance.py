"""add field_provenance JSONB column to expenses

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NOT NULL with a constant server_default backfills every existing row to
    # '{}' as part of this single statement (Postgres doesn't need a table
    # rewrite for a constant default since PG11+), and covers any INSERT that
    # doesn't explicitly set the column too — e.g. test fixtures seeding a
    # bare Expense row directly.
    op.add_column(
        "expenses",
        sa.Column(
            "field_provenance",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    # No new GRANT needed: migration 0001 already grants expensa_app
    # SELECT/INSERT/UPDATE/DELETE at the table level (GRANT ... ON ALL TABLES
    # IN SCHEMA public), which covers new columns added to an already-granted
    # table — Postgres privileges aren't column-scoped unless explicitly
    # declared that way, and none are here.


def downgrade() -> None:
    op.drop_column("expenses", "field_provenance")

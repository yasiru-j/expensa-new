"""add unique partial index on expenses(user_id, file_hash) for idempotency

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-26
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_expenses_user_hash_unique_live"


def upgrade() -> None:
    # A plain SELECT-then-INSERT idempotency check (what Phase 2 shipped) has
    # a race window: two concurrent identical uploads can both pass the
    # SELECT before either commits its INSERT, producing two rows and two
    # paid extractions for the same file. This unique index makes the
    # database itself the tiebreaker — the second INSERT is rejected
    # (handled at the app layer via ON CONFLICT DO NOTHING) rather than both
    # succeeding.
    #
    # It's a PARTIAL index (WHERE status <> 'failed') rather than a plain
    # unique constraint, so a previous failed attempt never blocks a fresh
    # retry of the same file — multiple 'failed' rows for the same
    # (user_id, file_hash) are allowed; at most one live (processing/ready/
    # confirmed) row is not.
    #
    # The existing non-unique idx_expenses_user_hash (migration 0001) stays —
    # it covers lookups across ALL statuses (e.g. future duplicate-detection
    # UX), which this partial index intentionally doesn't.
    #
    # No new GRANT needed: indexes aren't separately privileged in Postgres,
    # they inherit from the table, and expensa_app already has INSERT/SELECT
    # on expenses from migration 0001.
    op.execute(f"""
        CREATE UNIQUE INDEX {INDEX_NAME}
        ON expenses (user_id, file_hash)
        WHERE status <> 'failed'
        """)


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")

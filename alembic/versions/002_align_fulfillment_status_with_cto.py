"""align fulfillment status enum with CTO guidance

Revision ID: 002
Revises: 001
Create Date: 2026-09-08

Updates the fulfillment_status_enum PostgreSQL type:
- Renames OUTREACH_IN_PROGRESS → VENDOR_CONTACTED
- Renames ALTERNATE_NEEDED → ALTERNATE_REQUIRED
- Adds NO_RESPONSE
- Adds COMPLETED
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Rename existing values ---
    # ALTER TYPE ... RENAME VALUE requires PostgreSQL 10+
    op.execute("ALTER TYPE fulfillment_status_enum RENAME VALUE 'OUTREACH_IN_PROGRESS' TO 'VENDOR_CONTACTED'")
    op.execute("ALTER TYPE fulfillment_status_enum RENAME VALUE 'ALTERNATE_NEEDED' TO 'ALTERNATE_REQUIRED'")

    # --- Add new values ---
    # ALTER TYPE ... ADD VALUE is non-transactional in PG, so each must be
    # its own statement and cannot be rolled back within a transaction.
    op.execute("ALTER TYPE fulfillment_status_enum ADD VALUE IF NOT EXISTS 'NO_RESPONSE' AFTER 'REJECTED'")
    op.execute("ALTER TYPE fulfillment_status_enum ADD VALUE IF NOT EXISTS 'COMPLETED' AFTER 'ALTERNATE_REQUIRED'")


def downgrade() -> None:
    # WARNING: PostgreSQL does not support ALTER TYPE ... RENAME VALUE in reverse
    # or DROP VALUE from an enum. A full type recreation is required for downgrade.
    # This involves: creating a new type, migrating the column, dropping the old type,
    # and renaming the new type. Only implement if a downgrade is actually needed.
    #
    # Steps (manual, not automated here due to fragility):
    # 1. CREATE TYPE fulfillment_status_enum_old AS ENUM('PENDING','OUTREACH_IN_PROGRESS','CONFIRMED','REJECTED','ALTERNATE_NEEDED','CANCELLED');
    # 2. ALTER TABLE fulfillment_requests ALTER COLUMN status TYPE fulfillment_status_enum_old
    #      USING (CASE status::text
    #        WHEN 'VENDOR_CONTACTED' THEN 'OUTREACH_IN_PROGRESS'
    #        WHEN 'ALTERNATE_REQUIRED' THEN 'ALTERNATE_NEEDED'
    #        WHEN 'NO_RESPONSE' THEN 'REJECTED'
    #        WHEN 'COMPLETED' THEN 'CONFIRMED'
    #        ELSE status::text
    #      END)::fulfillment_status_enum_old;
    # 3. DROP TYPE fulfillment_status_enum;
    # 4. ALTER TYPE fulfillment_status_enum_old RENAME TO fulfillment_status_enum;
    raise NotImplementedError(
        "Downgrade requires manual enum type recreation. "
        "See comments in this migration for the required SQL steps."
    )

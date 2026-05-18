"""add linkedin email categories

Revision ID: 20260518_0013
Revises: 20260518_0012
Create Date: 2026-05-18 00:10:00
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260518_0013"
down_revision: Union[str, None] = "20260518_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE email_category ADD VALUE IF NOT EXISTS 'job_alert'")
    op.execute("ALTER TYPE email_category ADD VALUE IF NOT EXISTS 'application_confirmation'")


def downgrade() -> None:
    op.execute("UPDATE emails SET category = 'other' WHERE category IN ('job_alert', 'application_confirmation')")

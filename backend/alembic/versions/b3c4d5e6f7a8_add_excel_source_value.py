"""add_excel_source_value

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6_web_quotes_nullable_request_item_id_and_item_key
Create Date: 2026-10-12 00:00:00.000000

No DDL change: the purchases.source column is VARCHAR(20) with no CHECK
constraint, so the new "excel" value is already valid.  This migration
documents the addition of the value and serves as the chain link for
future migrations.
"""
from typing import Sequence, Union

from alembic import op  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No DDL needed — source column already accepts any VARCHAR(20) value."""
    pass


def downgrade() -> None:
    """No DDL to revert."""
    pass

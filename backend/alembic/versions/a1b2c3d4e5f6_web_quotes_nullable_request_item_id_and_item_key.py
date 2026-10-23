"""web_quotes: nullable request_item_id and item_key

Revision ID: a1b2c3d4e5f6
Revises: 0e9d76e3161d
Create Date: 2026-10-11 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '0e9d76e3161d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make request_item_id nullable to support standalone cache rows.
    op.alter_column('web_quotes', 'request_item_id', nullable=True)

    # Add item_key column (normalized item name, used for cache lookups).
    op.add_column('web_quotes', sa.Column('item_key', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_web_quotes_item_key'), 'web_quotes', ['item_key'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_web_quotes_item_key'), table_name='web_quotes')
    op.drop_column('web_quotes', 'item_key')
    op.alter_column('web_quotes', 'request_item_id', nullable=False)

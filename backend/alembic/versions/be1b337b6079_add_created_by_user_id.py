"""add requests.created_by_user_id

Revision ID: be1b337b6079
Revises: 76c83d65815a
Create Date: 2026-10-31 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'be1b337b6079'
down_revision: Union[str, Sequence[str], None] = '76c83d65815a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add created_by_user_id FK to requests (nullable for existing rows)."""
    # batch_alter_table so the SQLite fallback can add the FK too.
    with op.batch_alter_table('requests') as batch_op:
        batch_op.add_column(sa.Column('created_by_user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_requests_created_by_user_id',
            'users',
            ['created_by_user_id'], ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    """Remove created_by_user_id from requests."""
    with op.batch_alter_table('requests') as batch_op:
        batch_op.drop_constraint('fk_requests_created_by_user_id', type_='foreignkey')
        batch_op.drop_column('created_by_user_id')

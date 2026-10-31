"""decision log columns on audit_log (M19)

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-10-31 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8e9f0a1b2c3'
down_revision: Union[str, Sequence[str], None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add subject/decision/reason/role/outcome_tag/snapshot and backfill."""
    with op.batch_alter_table('audit_log') as batch_op:
        batch_op.add_column(sa.Column('subject_type', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('subject_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('decision', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('role', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('outcome_tag', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('snapshot', sa.JSON(), nullable=True))

    # Backfill: every existing row is a request_item approve/return. The role is
    # the user's current role; the snapshot was never recorded, so it stays NULL.
    op.execute(
        """
        UPDATE audit_log SET
            subject_type = 'request_item',
            subject_id = request_item_id,
            decision = action,
            reason = note,
            role = (SELECT users.role FROM users WHERE users.id = audit_log.user_id)
        """
    )
    # Rows without a request_item_id cannot be attributed to a subject.
    op.execute("UPDATE audit_log SET subject_id = 0 WHERE subject_id IS NULL")

    with op.batch_alter_table('audit_log') as batch_op:
        batch_op.alter_column('subject_type', existing_type=sa.String(20), nullable=False)
        batch_op.alter_column('subject_id', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('decision', existing_type=sa.String(20), nullable=False)

    op.create_index('ix_audit_log_subject', 'audit_log', ['subject_type', 'subject_id'])
    op.create_index('ix_audit_log_created_at', 'audit_log', ['created_at'])


def downgrade() -> None:
    """Drop the decision log columns."""
    op.drop_index('ix_audit_log_created_at', table_name='audit_log')
    op.drop_index('ix_audit_log_subject', table_name='audit_log')
    with op.batch_alter_table('audit_log') as batch_op:
        batch_op.drop_column('snapshot')
        batch_op.drop_column('outcome_tag')
        batch_op.drop_column('role')
        batch_op.drop_column('reason')
        batch_op.drop_column('decision')
        batch_op.drop_column('subject_id')
        batch_op.drop_column('subject_type')

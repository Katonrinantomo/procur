"""add quotations and quotation_lines (M18)

Revision ID: c7d8e9f0a1b2
Revises: be1b337b6079
Create Date: 2026-10-31 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = 'be1b337b6079'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create quotations and quotation_lines."""
    op.create_table(
        'quotations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_by_user_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_sha256', sa.String(64), nullable=False),
        sa.Column('vendor_name', sa.String(255), nullable=True),
        sa.Column('quote_no', sa.String(100), nullable=True),
        sa.Column('quote_date', sa.Date(), nullable=True),
        sa.Column('quote_total_idr', sa.BIGINT(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('check_error', sa.Text(), nullable=True),
        sa.Column('vendor_score', sa.Integer(), nullable=True),
        sa.Column('price_points', sa.Numeric(5, 1), nullable=True),
        sa.Column('arithmetic_ok', sa.Boolean(), nullable=True),
        sa.Column('covered_lines', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_lines', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('dropped_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('request_id', sa.Integer(), sa.ForeignKey('requests.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        'quotation_lines',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('quotation_id', sa.Integer(),
                  sa.ForeignKey('quotations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('line_no', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('qty', sa.Integer(), nullable=True),
        sa.Column('unit', sa.String(50), nullable=True),
        sa.Column('unit_price_idr', sa.BIGINT(), nullable=True),
        sa.Column('line_total_idr', sa.BIGINT(), nullable=True),
        sa.Column('item_id', sa.Integer(), sa.ForeignKey('items.id'), nullable=True),
        sa.Column('reference_unit_price_idr', sa.BIGINT(), nullable=True),
        sa.Column('reference_source', sa.String(20), nullable=False, server_default='none'),
        sa.Column('history_count', sa.Integer(), nullable=True),
        sa.Column('diff_pct', sa.Numeric(8, 1), nullable=True),
        sa.Column('band', sa.String(20), nullable=False, server_default='UNKNOWN'),
        sa.Column('recommendation', sa.String(20), nullable=True),
        sa.Column('search_query', sa.String(500), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=False),
        sa.Column('dropped', sa.JSON(), nullable=False),
    )
    op.create_index('ix_quotation_lines_quotation_id', 'quotation_lines', ['quotation_id'])


def downgrade() -> None:
    """Drop quotation_lines and quotations."""
    op.drop_index('ix_quotation_lines_quotation_id', table_name='quotation_lines')
    op.drop_table('quotation_lines')
    op.drop_table('quotations')

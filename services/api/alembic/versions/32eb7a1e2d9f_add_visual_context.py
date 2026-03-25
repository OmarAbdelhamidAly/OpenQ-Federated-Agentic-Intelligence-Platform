"""add visual_context

Revision ID: 32eb7a1e2d9f
Revises: 13ca700b24e2
Create Date: 2026-03-17 21:24:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '32eb7a1e2d9f'
down_revision: Union[str, None] = '13ca700b24e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('analysis_results', sa.Column('visual_context', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('analysis_results', 'visual_context')

"""add indexing_status to data_sources

Revision ID: 25aecfac38e9
Revises: 32eb7a1e2d9f
Create Date: 2026-03-17 22:51:42.646140
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '25aecfac38e9'
down_revision: Union[str, None] = '32eb7a1e2d9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add column as nullable first
    op.add_column('data_sources', sa.Column('indexing_status', sa.String(length=10), nullable=True))
    
    # 2. Set default value for existing rows
    op.execute("UPDATE data_sources SET indexing_status = 'done'")
    
    # 3. Make the column NOT NULL
    op.alter_column('data_sources', 'indexing_status', nullable=False)
    
    # Note: added drop_constraint keeping original autogenerate behavior
    op.drop_constraint('fk_analysis_jobs_kb', 'analysis_jobs', type_='foreignkey')


def downgrade() -> None:
    op.drop_column('data_sources', 'indexing_status')
    op.create_foreign_key('fk_analysis_jobs_kb', 'analysis_jobs', 'knowledge_bases', ['kb_id'], ['id'], ondelete='SET NULL')

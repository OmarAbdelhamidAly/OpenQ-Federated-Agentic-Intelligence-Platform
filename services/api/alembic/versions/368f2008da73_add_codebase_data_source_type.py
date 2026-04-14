"""Add codebase data source type

Revision ID: 368f2008da73
Revises: 47b9d3e8a2f1
Create Date: 2026-04-07 09:38:30.313805
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '368f2008da73'
down_revision: Union[str, None] = '47b9d3e8a2f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('ck_data_sources_type', 'data_sources', type_='check')
    op.create_check_constraint(
        'ck_data_sources_type', 
        'data_sources', 
        "type IN ('csv', 'sql', 'document', 'pdf', 'json', 'codebase')"
    )


def downgrade() -> None:
    op.drop_constraint('ck_data_sources_type', 'data_sources', type_='check')
    op.create_check_constraint(
        'ck_data_sources_type', 
        'data_sources', 
        "type IN ('csv', 'sql', 'document', 'pdf', 'json')"
    )

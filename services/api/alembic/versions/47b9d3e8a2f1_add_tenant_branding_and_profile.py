"""add tenant branding and profile fields

Revision ID: 47b9d3e8a2f1
Revises: 38be3fc64929
Create Date: 2026-03-24 03:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '47b9d3e8a2f1'
down_revision: Union[str, None] = '38be3fc64929'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('tenants', sa.Column('branding_config', sa.JSON(), nullable=True))

def downgrade() -> None:
    op.drop_column('tenants', 'branding_config')

"""add modulo_vistas to users

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-10-09
"""
from alembic import op
import sqlalchemy as sa

revision = 'c4d5e6f7a8b9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users',
        sa.Column('modulo_vistas', sa.Text(), nullable=True, server_default='{}')
    )


def downgrade():
    op.drop_column('users', 'modulo_vistas')

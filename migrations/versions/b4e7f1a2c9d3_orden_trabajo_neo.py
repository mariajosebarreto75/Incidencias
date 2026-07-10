"""orden_trabajo_neo

Revision ID: b4e7f1a2c9d3
Revises: 3f9c2e1a8b47
Create Date: 2026-06-17

"""
from alembic import op
import sqlalchemy as sa

revision = 'b4e7f1a2c9d3'
down_revision = '3f9c2e1a8b47'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'reportes_operacionales',
        sa.Column('orden_trabajo', sa.String(100), nullable=True)
    )


def downgrade():
    op.drop_column('reportes_operacionales', 'orden_trabajo')

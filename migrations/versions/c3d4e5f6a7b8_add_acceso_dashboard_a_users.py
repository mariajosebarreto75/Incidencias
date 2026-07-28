"""add acceso_dashboard a users

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('acceso_dashboard', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('acceso_dashboard', server_default=None)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('acceso_dashboard')

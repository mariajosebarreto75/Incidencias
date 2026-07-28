"""add editado_por y fecha_edicion a reportes_operacionales

Revision ID: a1b2c3d4e5f6
Revises: 62fa5af69161
Create Date: 2026-07-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '62fa5af69161'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('reportes_operacionales', schema=None) as batch_op:
        batch_op.add_column(sa.Column('editado_por', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('fecha_edicion', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('reportes_operacionales', schema=None) as batch_op:
        batch_op.drop_column('fecha_edicion')
        batch_op.drop_column('editado_por')

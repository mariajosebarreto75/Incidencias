"""conformidad_neo

Revision ID: 3f9c2e1a8b47
Revises: 08a17aad1274
Create Date: 2026-06-11 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3f9c2e1a8b47'
down_revision = '08a17aad1274'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('reportes_operacionales', schema=None) as batch_op:
        batch_op.add_column(sa.Column('conformidad_neo', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('observacion_conformidad', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('reportes_operacionales', schema=None) as batch_op:
        batch_op.drop_column('observacion_conformidad')
        batch_op.drop_column('conformidad_neo')

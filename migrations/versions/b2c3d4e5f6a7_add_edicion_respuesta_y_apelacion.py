"""add edicion de respuesta coordinador y apelacion no conformidad

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('reportes_operacionales', schema=None) as batch_op:
        batch_op.add_column(sa.Column('respuesta_editada', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('respuesta_editada_por', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('fecha_edicion_respuesta', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('apelacion_no_conformidad', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('apelado_por', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('fecha_apelacion', sa.DateTime(), nullable=True))
    with op.batch_alter_table('reportes_operacionales', schema=None) as batch_op:
        batch_op.alter_column('respuesta_editada', server_default=None)


def downgrade():
    with op.batch_alter_table('reportes_operacionales', schema=None) as batch_op:
        batch_op.drop_column('fecha_apelacion')
        batch_op.drop_column('apelado_por')
        batch_op.drop_column('apelacion_no_conformidad')
        batch_op.drop_column('fecha_edicion_respuesta')
        batch_op.drop_column('respuesta_editada_por')
        batch_op.drop_column('respuesta_editada')

"""add indexes to reporte_operacional for performance

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-10-08
"""
from alembic import op

revision = 'a2b3c4d5e6f7'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_reporte_fecha_reporte',  'reportes_operacionales', ['fecha_reporte'],  unique=False)
    op.create_index('ix_reporte_contrato',        'reportes_operacionales', ['contrato'],        unique=False)
    op.create_index('ix_reporte_recurso',         'reportes_operacionales', ['recurso'],          unique=False)
    op.create_index('ix_reporte_estado',          'reportes_operacionales', ['estado'],           unique=False)
    op.create_index('ix_reporte_conformidad_neo', 'reportes_operacionales', ['conformidad_neo'],  unique=False)
    op.create_index('ix_reporte_contrato_fecha',  'reportes_operacionales', ['contrato', 'fecha_reporte'], unique=False)
    op.create_index('ix_reporte_estado_conf',     'reportes_operacionales', ['estado', 'conformidad_neo'], unique=False)


def downgrade():
    op.drop_index('ix_reporte_estado_conf',     table_name='reportes_operacionales')
    op.drop_index('ix_reporte_contrato_fecha',  table_name='reportes_operacionales')
    op.drop_index('ix_reporte_conformidad_neo', table_name='reportes_operacionales')
    op.drop_index('ix_reporte_estado',          table_name='reportes_operacionales')
    op.drop_index('ix_reporte_recurso',         table_name='reportes_operacionales')
    op.drop_index('ix_reporte_contrato',        table_name='reportes_operacionales')
    op.drop_index('ix_reporte_fecha_reporte',   table_name='reportes_operacionales')

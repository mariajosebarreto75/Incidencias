"""add indexes to horas_extras for performance

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-10-08
"""
from alembic import op

revision = 'b3c4d5e6f7a8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_he_contrato_id',    'horas_extras', ['contrato_id'], unique=False)
    op.create_index('ix_he_fecha_labor',     'horas_extras', ['fecha_labor'],  unique=False)
    op.create_index('ix_he_cedula',          'horas_extras', ['cedula'],       unique=False)
    op.create_index('ix_he_estado',          'horas_extras', ['estado'],       unique=False)
    op.create_index('ix_he_corte_id',        'horas_extras', ['corte_id'],     unique=False)
    op.create_index('ix_he_contrato_fecha',  'horas_extras', ['contrato_id', 'fecha_labor'], unique=False)
    op.create_index('ix_he_corte_estado',    'horas_extras', ['corte_id', 'estado'],         unique=False)


def downgrade():
    op.drop_index('ix_he_corte_estado',    table_name='horas_extras')
    op.drop_index('ix_he_contrato_fecha',  table_name='horas_extras')
    op.drop_index('ix_he_corte_id',        table_name='horas_extras')
    op.drop_index('ix_he_estado',          table_name='horas_extras')
    op.drop_index('ix_he_cedula',          table_name='horas_extras')
    op.drop_index('ix_he_fecha_labor',     table_name='horas_extras')
    op.drop_index('ix_he_contrato_id',     table_name='horas_extras')

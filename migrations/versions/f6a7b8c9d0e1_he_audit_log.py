"""tabla he_audit_log para auditoría de horas extras

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa

revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'he_audit_log',
        sa.Column('id',           sa.Integer(),     nullable=False),
        sa.Column('operacion',    sa.String(20),    nullable=False),
        sa.Column('registro_id',  sa.Integer(),     nullable=True),
        sa.Column('contrato_id',  sa.Integer(),     nullable=True),
        sa.Column('contrato_nom', sa.String(200),   nullable=True),
        sa.Column('fecha_labor',  sa.Date(),        nullable=True),
        sa.Column('cedula',       sa.String(50),    nullable=True),
        sa.Column('nombre',       sa.String(200),   nullable=True),
        sa.Column('horas_rep',    sa.Numeric(6, 2), nullable=True),
        sa.Column('id_concepto',  sa.String(10),    nullable=True),
        sa.Column('tipo_he',      sa.String(200),   nullable=True),
        sa.Column('estado_antes', sa.String(30),    nullable=True),
        sa.Column('estado_desp',  sa.String(30),    nullable=True),
        sa.Column('datos_antes',  sa.Text(),        nullable=True),
        sa.Column('datos_desp',   sa.Text(),        nullable=True),
        sa.Column('usuario_id',   sa.Integer(),     nullable=True),
        sa.Column('usuario_nom',  sa.String(200),   nullable=True),
        sa.Column('usuario_rol',  sa.String(50),    nullable=True),
        sa.Column('ip',           sa.String(60),    nullable=True),
        sa.Column('fecha',        sa.DateTime(),    nullable=False),
        sa.ForeignKeyConstraint(['usuario_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_he_audit_log_registro_id', 'he_audit_log', ['registro_id'])
    op.create_index('ix_he_audit_log_contrato_id', 'he_audit_log', ['contrato_id'])
    op.create_index('ix_he_audit_log_fecha',       'he_audit_log', ['fecha'])


def downgrade():
    op.drop_index('ix_he_audit_log_fecha',       table_name='he_audit_log')
    op.drop_index('ix_he_audit_log_contrato_id', table_name='he_audit_log')
    op.drop_index('ix_he_audit_log_registro_id', table_name='he_audit_log')
    op.drop_table('he_audit_log')

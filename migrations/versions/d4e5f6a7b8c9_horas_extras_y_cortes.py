"""horas_extras tabla y he_cortes

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def _has_table(conn, name):
    return Inspector.from_engine(conn).has_table(name)


def _has_column(conn, table, col):
    cols = [c['name'] for c in Inspector.from_engine(conn).get_columns(table)]
    return col in cols


def upgrade():
    conn = op.get_bind()

    # ── he_cortes ────────────────────────────────────────────────────────────
    if not _has_table(conn, 'he_cortes'):
        op.create_table(
            'he_cortes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('nombre', sa.String(100), nullable=False),
            sa.Column('fecha_inicio', sa.Date(), nullable=False),
            sa.Column('fecha_fin', sa.Date(), nullable=False),
            sa.Column('estado', sa.String(20), server_default='ABIERTO'),
            sa.Column('contrato_id', sa.Integer(), sa.ForeignKey('contratos.id')),
            sa.Column('creado_por_id', sa.Integer(), sa.ForeignKey('users.id')),
            sa.Column('cerrado_por_id', sa.Integer(), sa.ForeignKey('users.id')),
            sa.Column('fecha_creacion', sa.DateTime()),
            sa.Column('fecha_cierre', sa.DateTime()),
            sa.Column('observacion', sa.Text()),
        )

    # ── horas_extras ─────────────────────────────────────────────────────────
    if not _has_table(conn, 'horas_extras'):
        op.create_table(
            'horas_extras',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('contrato_id', sa.Integer(), sa.ForeignKey('contratos.id'), nullable=False),
            sa.Column('fecha_labor', sa.Date(), nullable=False),
            sa.Column('cedula', sa.String(50), nullable=False),
            sa.Column('nombre', sa.String(200)),
            sa.Column('recurso', sa.String(200)),
            sa.Column('id_concepto', sa.String(10), nullable=False),
            sa.Column('tipo_he', sa.String(200)),
            sa.Column('horas_reportadas', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('horas_compensadas', sa.Integer(), server_default='0'),
            sa.Column('placa', sa.String(20)),
            sa.Column('hora_inicio', sa.String(10)),
            sa.Column('hora_fin', sa.String(10)),
            sa.Column('autorizacion_sup', sa.String(200)),
            sa.Column('justificacion', sa.Text()),
            sa.Column('observacion', sa.Text()),
            sa.Column('valor_hora', sa.Numeric(14, 2)),
            sa.Column('valor_extra_nomina', sa.Numeric(14, 2)),
            sa.Column('valor_extra', sa.Numeric(14, 2)),
            sa.Column('autorizacion_neo', sa.String(30)),
            sa.Column('horas_autorizadas', sa.Integer()),
            sa.Column('obs_neo', sa.Text()),
            sa.Column('estado', sa.String(30), server_default='PENDIENTE'),
            sa.Column('reportado_por_id', sa.Integer(), sa.ForeignKey('users.id')),
            sa.Column('fecha_reporte', sa.DateTime()),
            sa.Column('validado_por_id', sa.Integer(), sa.ForeignKey('users.id')),
            sa.Column('fecha_validacion', sa.DateTime()),
            sa.Column('corte_id', sa.Integer(), sa.ForeignKey('he_cortes.id')),
        )
    else:
        # Tabla ya existe — agregar columnas faltantes
        cols_nuevas = [
            ('placa',             sa.String(20)),
            ('hora_inicio',       sa.String(10)),
            ('hora_fin',          sa.String(10)),
            ('autorizacion_sup',  sa.String(200)),
            ('valor_hora',        sa.Numeric(14, 2)),
            ('valor_extra_nomina',sa.Numeric(14, 2)),
            ('valor_extra',       sa.Numeric(14, 2)),
            ('autorizacion_neo',  sa.String(30)),
            ('horas_autorizadas', sa.Integer()),
            ('obs_neo',           sa.Text()),
            ('estado',            sa.String(30)),
            ('reportado_por_id',  sa.Integer()),
            ('fecha_reporte',     sa.DateTime()),
            ('validado_por_id',   sa.Integer()),
            ('fecha_validacion',  sa.DateTime()),
            ('corte_id',          sa.Integer()),
        ]
        for col_name, col_type in cols_nuevas:
            if not _has_column(conn, 'horas_extras', col_name):
                op.add_column('horas_extras', sa.Column(col_name, col_type))

        # Renombrar supervisor → autorizacion_sup si aún existe el viejo nombre
        if _has_column(conn, 'horas_extras', 'supervisor') and not _has_column(conn, 'horas_extras', 'autorizacion_sup'):
            op.alter_column('horas_extras', 'supervisor', new_column_name='autorizacion_sup')

        # FK corte_id si no existe
        insp = Inspector.from_engine(conn)
        fk_names = [fk['name'] for fk in insp.get_foreign_keys('horas_extras')]
        if 'fk_horas_extras_corte_id' not in fk_names and _has_column(conn, 'horas_extras', 'corte_id'):
            try:
                op.create_foreign_key(
                    'fk_horas_extras_corte_id',
                    'horas_extras', 'he_cortes',
                    ['corte_id'], ['id']
                )
            except Exception:
                pass  # puede ya existir sin nombre conocido


def downgrade():
    pass

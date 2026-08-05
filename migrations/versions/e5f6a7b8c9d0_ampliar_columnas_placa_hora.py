"""ampliar columnas placa hora_inicio hora_fin

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('horas_extras', 'placa',      existing_type=sa.String(20),  type_=sa.String(50),  existing_nullable=True)
    op.alter_column('horas_extras', 'hora_inicio', existing_type=sa.String(10), type_=sa.String(20), existing_nullable=True)
    op.alter_column('horas_extras', 'hora_fin',    existing_type=sa.String(10), type_=sa.String(20), existing_nullable=True)


def downgrade():
    pass

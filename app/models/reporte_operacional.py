from app.extensions import db

from datetime import datetime


class ReporteOperacional(db.Model):

    __tablename__ = "reportes_operacionales"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # =====================
    # FECHAS
    # =====================

    fecha_reporte = db.Column(
        db.Date,
        nullable=False
    )

    fecha_creado = db.Column(
        db.DateTime,
        default=datetime.now
    )

    # =====================
    # DATOS OPERATIVOS
    # =====================

    contrato = db.Column(
        db.String(250),
        nullable=False
    )

    recurso = db.Column(
        db.String(150),
        nullable=False
    )

    placa = db.Column(
        db.String(20)
    )

    tipo_cuadrilla = db.Column(
        db.String(150)
    )

    meta = db.Column(
        db.Float
    )

    tipo_actividad = db.Column(
        db.String(150)
    )

    orden_trabajo = db.Column(
        db.String(100)
    )

    # =====================
    # INCIDENCIA
    # =====================

    hora_inicio = db.Column(
        db.Time,
        nullable=False
    )

    hora_fin = db.Column(
        db.Time,
        nullable=False
    )

    tipo_incidencia = db.Column(
        db.String(200),
        nullable=False
    )

    parametro_neo = db.Column(
        db.String(200),
        nullable=False
    )

    observacion = db.Column(
        db.Text
    )

    # =====================
    # CALCULADOS
    # =====================

    duracion = db.Column(
        db.String(20)
    )

    impacto = db.Column(
        db.String(50)
    )

    horas_afectadas = db.Column(
        db.Float
    )

    afectacion_economica = db.Column(
        db.Float
    )

    # =====================
    # EVIDENCIAS
    # =====================

    evidencia_1 = db.Column(
        db.String(300),
        nullable=False
    )

    evidencia_2 = db.Column(
        db.String(300)
    )

    # =====================
    # AUDITORIA NEO
    # =====================

    reportado_por = db.Column(
        db.String(150)
    )

    estado = db.Column(
        db.String(50),
        default="Abierto"
    )

    # =====================
    # RESPUESTA COORDINADOR
    # =====================

    respuesta = db.Column(
        db.Text
    )

    parametro_coordinador = db.Column(
        db.String(200)
    )

    evidencia_coor_1 = db.Column(
        db.String(300)
    )

    evidencia_coor_2 = db.Column(
        db.String(300)
    )

    estado_conformidad = db.Column(
        db.String(100)
    )

    accion_a_tomar = db.Column(
        db.String(200)
    )

    respondido_por = db.Column(
        db.String(150)
    )

    fecha_respuesta = db.Column(
        db.DateTime
    )

    # =====================
    # VALIDACIÓN NEO
    # =====================

    conformidad_neo = db.Column(
        db.String(100)
    )

    observacion_conformidad = db.Column(
        db.Text
    )

    def __repr__(self):

        return (
            f"<Reporte {self.id}>"
        )
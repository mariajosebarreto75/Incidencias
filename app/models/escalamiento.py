from datetime import datetime
from app.extensions import db


# Tipos de incidencia que activan el escalamiento
TIPOS_ESCALABLES = {"Fuera de ruta", "Salida tardía", "Tiempo muerto", "Terminación temprana"}

# Estados del ciclo de vida
# supervisor_notificado → esperando_neo_1 → coordinador_notificado
# → esperando_neo_2 → director_notificado → gerencia_notificada
# En cualquier momento: cerrado_gestionado | cerrado_sin_gestion
ESTADOS_ESCALAMIENTO = (
    "supervisor_notificado",
    "esperando_neo_1",
    "coordinador_notificado",
    "esperando_neo_2",
    "director_notificado",
    "gerencia_notificada",
    "cerrado_gestionado",
    "cerrado_sin_gestion",
)


class EscalamientoIncidencia(db.Model):
    __tablename__ = "escalamientos_incidencia"

    id = db.Column(db.Integer, primary_key=True)

    reporte_id = db.Column(
        db.Integer, db.ForeignKey("reportes_operacionales.id"), nullable=False, index=True
    )
    reporte = db.relationship("ReporteOperacional", backref="escalamientos", lazy="select")

    estado = db.Column(db.String(40), nullable=False, default="supervisor_notificado")

    # Cuándo se envió la notificación del estado actual (para calcular el timeout)
    notificado_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Respuesta de NEO a la pregunta "¿sigue presentándose?"
    # None = no ha respondido, True = sí sigue, False = ya no
    respuesta_neo = db.Column(db.Boolean, nullable=True)
    respuesta_neo_at = db.Column(db.DateTime, nullable=True)

    # Quién gestionó (cerró) el escalamiento
    gestionado_por = db.Column(db.String(100), nullable=True)   # username
    gestionado_at = db.Column(db.DateTime, nullable=True)
    notas_gestion = db.Column(db.Text, nullable=True)

    creado_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Escalamiento reporte={self.reporte_id} estado={self.estado}>"

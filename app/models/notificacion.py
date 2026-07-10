from datetime import datetime
from app.extensions import db


class Notificacion(db.Model):
    __tablename__ = "notificaciones"

    id               = db.Column(db.Integer, primary_key=True)
    usuario_destino  = db.Column(db.String(100), nullable=False, index=True)  # username
    tipo             = db.Column(db.String(50),  nullable=False)
    # tipos: nuevo_reporte | reporte_respondido | no_conforme
    reporte_id       = db.Column(db.Integer, nullable=False)
    mensaje          = db.Column(db.String(300), nullable=False)
    # datos del reporte para mostrar en la tarjeta
    contrato         = db.Column(db.String(200))
    recurso          = db.Column(db.String(200))
    fecha_reporte    = db.Column(db.String(20))
    tipo_incidencia  = db.Column(db.String(200))

    gestionada       = db.Column(db.Boolean, default=False, nullable=False)
    fecha_creacion   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Notificacion {self.tipo} → {self.usuario_destino} reporte={self.reporte_id}>"

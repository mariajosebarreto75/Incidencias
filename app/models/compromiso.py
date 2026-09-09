from datetime import date
from app.extensions import db


class Compromiso(db.Model):
    __tablename__ = "compromisos"

    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey("contratos.id"), nullable=False, index=True)
    responsable = db.Column(db.String(200), nullable=False)
    compromiso = db.Column(db.Text, nullable=False)
    observacion_general = db.Column(db.Text)

    fecha_creacion = db.Column(db.Date, nullable=False, default=date.today)
    fecha_entrega = db.Column(db.Date, nullable=False)
    fecha_entrega_real = db.Column(db.Date)

    estado = db.Column(db.String(30), nullable=False, default="Pendiente")
    cantidad_reprogramaciones = db.Column(db.Integer, nullable=False, default=0)

    evidencia_path = db.Column(db.String(500))
    evidencia_nombre = db.Column(db.String(200))

    contrato = db.relationship("Contrato", backref=db.backref("compromisos", lazy="dynamic"))
    historial = db.relationship("HistorialReprogramacion", back_populates="compromiso",
                                cascade="all, delete-orphan", order_by="HistorialReprogramacion.id")

    @property
    def atrasado(self):
        return self.estado != "Cerrado" and self.fecha_entrega < date.today()


class HistorialReprogramacion(db.Model):
    __tablename__ = "historial_reprogramaciones"

    id = db.Column(db.Integer, primary_key=True)
    compromiso_id = db.Column(db.Integer, db.ForeignKey("compromisos.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    fecha_anterior = db.Column(db.Date, nullable=False)
    nueva_fecha = db.Column(db.Date, nullable=False)
    fecha_cambio = db.Column(db.DateTime, nullable=False, default=db.func.now())

    compromiso = db.relationship("Compromiso", back_populates="historial")

from datetime import datetime
from app.extensions import db


class ParqCliente(db.Model):
    __tablename__ = "parq_clientes"

    id               = db.Column(db.Integer, primary_key=True)
    nombre           = db.Column(db.String(200), nullable=False)
    cedula           = db.Column(db.String(20))
    telefono         = db.Column(db.String(20))
    placa            = db.Column(db.String(20), nullable=False, unique=True, index=True)
    tipo_vehiculo    = db.Column(db.String(10), nullable=False)   # carro | moto
    tarifa_mensual   = db.Column(db.Numeric(12, 2), nullable=False)
    dia_corte        = db.Column(db.Integer, nullable=False)       # 1-31
    fecha_inicio     = db.Column(db.Date, nullable=False)
    activo           = db.Column(db.Boolean, default=True, nullable=False)
    observaciones    = db.Column(db.Text)
    creado_por       = db.Column(db.String(100))
    creado_en        = db.Column(db.DateTime, default=datetime.now, nullable=False)
    actualizado_en   = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    pagos  = db.relationship("ParqPago",   back_populates="cliente", lazy="dynamic")

    def __repr__(self):
        return f"<ParqCliente {self.placa} – {self.nombre}>"

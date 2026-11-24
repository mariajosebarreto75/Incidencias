from datetime import datetime
from app.extensions import db


class ParqTarifa(db.Model):
    __tablename__ = "parq_tarifas"

    id             = db.Column(db.Integer, primary_key=True)
    tipo_vehiculo  = db.Column(db.String(10), nullable=False, unique=True)  # carro | moto
    valor          = db.Column(db.Numeric(12, 2), nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    actualizado_por = db.Column(db.String(100))

    def __repr__(self):
        return f"<ParqTarifa {self.tipo_vehiculo}={self.valor}>"

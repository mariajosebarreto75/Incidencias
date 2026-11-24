from datetime import datetime
from app.extensions import db


class ParqSalida(db.Model):
    __tablename__ = "parq_salidas"

    id              = db.Column(db.Integer, primary_key=True)
    fecha           = db.Column(db.Date, nullable=False)
    categoria       = db.Column(db.String(30), nullable=False)
    # nomina | servicios_publicos | arriendo | mantenimiento | aseo | otros
    descripcion     = db.Column(db.Text, nullable=False)
    valor           = db.Column(db.Numeric(12, 2), nullable=False)
    medio           = db.Column(db.String(20), nullable=False)   # efectivo | transferencia
    registrado_por  = db.Column(db.String(100))
    creado_en       = db.Column(db.DateTime, default=datetime.now, nullable=False)
    # Borrado lógico
    eliminado       = db.Column(db.Boolean, default=False, nullable=False)
    eliminado_por   = db.Column(db.String(100))
    eliminado_en    = db.Column(db.DateTime)

    def __repr__(self):
        return f"<ParqSalida {self.categoria} ${self.valor} {self.fecha}>"

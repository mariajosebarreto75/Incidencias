from datetime import datetime
from app.extensions import db


class ParqCierre(db.Model):
    __tablename__ = "parq_cierres_caja"

    id                 = db.Column(db.Integer, primary_key=True)
    fecha              = db.Column(db.Date, nullable=False, unique=True)
    efectivo_esperado  = db.Column(db.Numeric(12, 2), nullable=False)
    efectivo_contado   = db.Column(db.Numeric(12, 2), nullable=False)
    diferencia         = db.Column(db.Numeric(12, 2), nullable=False)
    observacion        = db.Column(db.Text)
    cerrado_por        = db.Column(db.String(100))
    creado_en          = db.Column(db.DateTime, default=datetime.now, nullable=False)

    def __repr__(self):
        return f"<ParqCierre {self.fecha} dif={self.diferencia}>"

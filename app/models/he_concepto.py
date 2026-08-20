from app.extensions import db


class HeConcepto(db.Model):
    __tablename__ = "he_conceptos"

    id      = db.Column(db.Integer, primary_key=True)
    codigo  = db.Column(db.String(10), nullable=False, unique=True)
    nombre  = db.Column(db.String(200), nullable=False)
    factor  = db.Column(db.Numeric(6, 4), nullable=False, default=1)
    activo  = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id":     self.id,
            "codigo": self.codigo,
            "nombre": self.nombre,
            "factor": float(self.factor),
            "activo": self.activo,
        }

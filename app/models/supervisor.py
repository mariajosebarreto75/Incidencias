from app.extensions import db


class Supervisor(db.Model):
    __tablename__ = "supervisores"

    id          = db.Column(db.Integer, primary_key=True)
    nombre      = db.Column(db.String(200), nullable=False, unique=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey("contratos.id"), nullable=True)
    activo      = db.Column(db.Boolean, default=True, nullable=False)

    contrato = db.relationship("Contrato", backref="supervisores")

    def to_dict(self):
        return {
            "id":          self.id,
            "nombre":      self.nombre,
            "contrato_id": self.contrato_id,
            "contrato":    self.contrato.contrato if self.contrato else "",
            "activo":      self.activo,
        }

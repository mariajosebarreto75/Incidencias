from app.extensions import db

supervisor_contrato = db.Table(
    "supervisor_contrato",
    db.Column("supervisor_id", db.Integer, db.ForeignKey("supervisores.id"), primary_key=True),
    db.Column("contrato_id",   db.Integer, db.ForeignKey("contratos.id"),    primary_key=True),
)


class Supervisor(db.Model):
    __tablename__ = "supervisores"

    id     = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False, unique=True)
    activo = db.Column(db.Boolean, default=True, nullable=False)

    contratos = db.relationship(
        "Contrato",
        secondary=supervisor_contrato,
        backref="supervisores",
        lazy="select",
    )

    def to_dict(self):
        return {
            "id":          self.id,
            "nombre":      self.nombre,
            "activo":      self.activo,
            "contrato_ids": [c.id for c in self.contratos],
            "contratos":   [c.contrato for c in self.contratos],
        }

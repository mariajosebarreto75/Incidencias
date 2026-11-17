from app.extensions import db


class HeJerarquia(db.Model):
    """Director que aprueba las horas extras que reporta cada coordinador
    (contratos con jerarquía de aprobación, ej. Administración General)."""

    __tablename__ = "he_jerarquia"

    id             = db.Column(db.Integer, primary_key=True)
    coordinador_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    director_id    = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

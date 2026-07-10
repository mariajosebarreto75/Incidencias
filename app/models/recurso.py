from app.extensions import db


class Recurso(
    db.Model
):

    __tablename__ = "recursos"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    recurso = db.Column(
        db.String(200),
        unique=True,
        nullable=False
    )

    tipo_cuadrilla = db.Column(
        db.String(200)
    )

    meta = db.Column(
        db.Float
    )

    activo = db.Column(
        db.Boolean,
        default=True
    )
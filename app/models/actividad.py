from app.extensions import db


class Actividad(db.Model):

    __tablename__ = "actividades"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    actividad = db.Column(
        db.Text,
        nullable=False
    )

    contrato = db.Column(
        db.String(250)
    )
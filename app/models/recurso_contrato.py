from app.extensions import db


class RecursoContrato(
    db.Model
):

    __tablename__ = (
        "recurso_contrato"
    )

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    contrato = db.Column(
        db.Text,
        nullable=False
    )

    recurso = db.Column(
        db.String(200),
        nullable=False
    )
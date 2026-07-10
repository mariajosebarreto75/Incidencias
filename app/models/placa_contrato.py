from app.extensions import db


class PlacaContrato(
    db.Model
):

    __tablename__ = (
        "placa_contrato"
    )

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    placa = db.Column(
        db.String(50),
        nullable=False
    )

    contrato = db.Column(
        db.Text,
        nullable=False
    )
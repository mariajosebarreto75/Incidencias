from app.extensions import db


class UserContrato(db.Model):

    __tablename__ = "user_contratos"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        nullable=False,
        index=True
    )

    contrato = db.Column(
        db.String(250),
        nullable=False
    )

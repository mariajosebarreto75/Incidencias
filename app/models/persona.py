from app.extensions import db


class Persona(db.Model):

    __tablename__ = "personas"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    Cargo = db.Column(
        db.String(150),
        nullable=False
    )

    Documento = db.Column(
        db.String(50),
        nullable=False,
        unique=True
    )

    Salario = db.Column(
        db.Float,
        nullable=True
    )

    Nombre = db.Column(
        db.String(200),
        nullable=False
    )

    def __repr__(self):

        return (
            f"<Persona {self.Nombre}>"
        )
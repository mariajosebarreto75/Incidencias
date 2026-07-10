from app.extensions import db


class ParametroNeo(db.Model):

    __tablename__ = "parametros_neo"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    parametroNeo = db.Column(
        db.String(200),
        nullable=False,
        unique=True
    )

    def __repr__(self):

        return (
            f"<Parametro {self.parametroNeo}>"
        )
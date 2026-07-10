from app.extensions import db


class TipoDesvio(db.Model):

    __tablename__ = "tipos_desvio"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    tipo_desvio = db.Column(
        db.String(200),
        nullable=False,
        unique=True
    )

    def __repr__(self):

        return (
            f"<Desvio {self.tipo_desvio}>"
        )
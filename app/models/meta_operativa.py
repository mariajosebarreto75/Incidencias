from app.extensions import db


class MetaOperativa(db.Model):

    __tablename__ = "metas_operativas"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    Tipo_cuadrilla = db.Column(
        db.String(150),
        nullable=False
    )

    Proceso = db.Column(
        db.String(150),
        nullable=True
    )

    Meta_Produccion = db.Column(
        db.Float,
        nullable=False
    )

    contrato = db.Column(
        db.String(250),
        nullable=False
    )

    def __repr__(self):

        return (
            f"<Meta {self.contrato}>"
        )
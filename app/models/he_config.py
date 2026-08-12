from app.extensions import db


class HeConfig(db.Model):
    __tablename__ = "he_config"

    id    = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.Text, default="")

    @classmethod
    def get(cls, clave, default=""):
        obj = cls.query.filter_by(clave=clave).first()
        return obj.valor if obj else default

    @classmethod
    def set(cls, clave, valor):
        obj = cls.query.filter_by(clave=clave).first()
        if obj:
            obj.valor = valor
        else:
            db.session.add(cls(clave=clave, valor=valor))
        db.session.commit()

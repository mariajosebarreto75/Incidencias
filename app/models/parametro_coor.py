from app.extensions import db


class ParametroCoor(db.Model):

    __tablename__ = "parametros_coor"

    id = db.Column(db.Integer, primary_key=True)

    parametro = db.Column(db.String(200), nullable=False, unique=True)

    def __repr__(self):
        return f"<ParametroCoor {self.parametro}>"

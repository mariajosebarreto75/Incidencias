from app.extensions import db


class AccionTomar(db.Model):

    __tablename__ = "acciones_tomar"

    id = db.Column(db.Integer, primary_key=True)

    accion = db.Column(db.String(250), nullable=False, unique=True)

    def __repr__(self):
        return f"<AccionTomar {self.accion}>"

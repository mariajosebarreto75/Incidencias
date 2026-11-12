from app.extensions import db


class PersonalHesego(db.Model):
    __tablename__ = "personal_hesego"

    id     = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(300), nullable=False)
    correo = db.Column(db.String(200), nullable=False, unique=True, index=True)

    def __repr__(self):
        return f"<PersonalHesego {self.nombre} <{self.correo}>>"

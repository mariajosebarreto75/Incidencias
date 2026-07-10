from app.extensions import db


class Contrato(db.Model):

    __tablename__ = "contratos"

    id = db.Column(db.Integer, primary_key=True)

    # Código corto único — ej: "021C", "2876BLYR", "CW356942"
    codigo = db.Column(db.String(50), nullable=True, unique=True, index=True)

    # Nombre corto — ej: "021 OYMM CHAPARRAL"
    nombre = db.Column(db.String(200), nullable=True)

    # Sede — ej: "Chaparral", "Espinal", "Buga" (informativo)
    sede = db.Column(db.String(150), nullable=True)

    # Proceso — ej: "OYMM", "LYR", "MTTO", "ARBORICULTURA"
    proceso = db.Column(db.String(100), nullable=True)

    # Nombre completo de display — ej: "Tolima (021) - OyMM - Chaparral"
    # Este campo es la clave usada en todo el sistema (UserContrato, RecursoContrato, etc.)
    contrato = db.Column(db.String(200), nullable=False, unique=True)

    coordinador = db.Column(db.String(150), nullable=True)
    director    = db.Column(db.String(150), nullable=True)

    activo = db.Column(db.Boolean, nullable=False, default=True, server_default="TRUE")

    def __repr__(self):
        return f"<Contrato {self.codigo or self.contrato}>"

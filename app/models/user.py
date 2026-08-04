import json
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class User(
    db.Model,
    UserMixin
):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    nombre_completo = db.Column(
        db.String(200),
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    rol = db.Column(
        db.String(50),
        nullable=False
    )

    contrato = db.Column(
        db.String(200)
    )

    activo = db.Column(
        db.Boolean,
        default=True
    )

    acceso_dashboard = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    # Lista de permisos de módulos extra, ej: ["horas_extras", "seguimiento"]
    permisos = db.Column(db.Text, default="[]", nullable=False, server_default="[]")

    # ======================
    # PERMISOS
    # ======================

    def get_permisos(self):
        try:
            return json.loads(self.permisos or "[]")
        except Exception:
            return []

    def tiene_permiso(self, permiso):
        if self.rol and self.rol.lower() == "admin":
            return True
        return permiso in self.get_permisos()

    def set_permiso(self, permiso, valor: bool):
        lista = self.get_permisos()
        if valor and permiso not in lista:
            lista.append(permiso)
        elif not valor and permiso in lista:
            lista.remove(permiso)
        self.permisos = json.dumps(lista)

    # ======================
    # PASSWORD
    # ======================

    def set_password(
        self,
        password
    ):

        self.password_hash = (
            generate_password_hash(
                password
            )
        )

    def check_password(
        self,
        password
    ):

        return check_password_hash(
            self.password_hash,
            password
        )
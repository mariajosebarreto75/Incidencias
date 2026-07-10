from flask_login import UserMixin

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

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
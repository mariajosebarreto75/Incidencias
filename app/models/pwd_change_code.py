import hashlib
import secrets
from datetime import datetime, timedelta
from app.extensions import db

EXPIRY_MINUTES  = 10
MAX_ATTEMPTS    = 5
MAX_REENVIOS    = 3


class PwdChangeCode(db.Model):
    __tablename__ = "pwd_change_codes"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code_hash  = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used       = db.Column(db.Boolean, default=False, nullable=False)
    attempts   = db.Column(db.Integer, default=0, nullable=False)
    reenvios   = db.Column(db.Integer, default=0, nullable=False)

    @staticmethod
    def _hash(code: str) -> str:
        return hashlib.sha256(code.encode()).hexdigest()

    @classmethod
    def generar(cls, user_id: int) -> str:
        """Invalida códigos anteriores y genera uno nuevo. Devuelve el código en texto plano."""
        registro_anterior = cls.query.filter_by(user_id=user_id).order_by(cls.id.desc()).first()
        reenvios_actuales = (registro_anterior.reenvios if registro_anterior else 0)

        code = f"{secrets.randbelow(1_000_000):06d}"
        cls.query.filter_by(user_id=user_id, used=False).delete()

        nuevo = cls(
            user_id    = user_id,
            code_hash  = cls._hash(code),
            expires_at = datetime.utcnow() + timedelta(minutes=EXPIRY_MINUTES),
            reenvios   = reenvios_actuales,
        )
        db.session.add(nuevo)
        db.session.commit()
        return code

    @classmethod
    def reenviar(cls, user_id: int):
        """Genera un nuevo código contabilizando el reenvío. Lanza ValueError si excede el límite."""
        ultimo = cls.query.filter_by(user_id=user_id).order_by(cls.id.desc()).first()
        reenvios = (ultimo.reenvios if ultimo else 0) + 1
        if reenvios > MAX_REENVIOS:
            raise ValueError("Límite de reenvíos alcanzado")

        cls.query.filter_by(user_id=user_id, used=False).delete()
        code = f"{secrets.randbelow(1_000_000):06d}"
        nuevo = cls(
            user_id    = user_id,
            code_hash  = cls._hash(code),
            expires_at = datetime.utcnow() + timedelta(minutes=EXPIRY_MINUTES),
            reenvios   = reenvios,
        )
        db.session.add(nuevo)
        db.session.commit()
        return code

    @classmethod
    def verificar(cls, user_id: int, code: str):
        """
        Verifica el código. Devuelve True si es válido.
        Lanza ValueError con mensaje claro si no lo es.
        """
        registro = cls.query.filter_by(
            user_id=user_id, used=False
        ).order_by(cls.id.desc()).first()

        if not registro:
            raise ValueError("No hay código activo. Solicita uno nuevo.")

        if registro.used:
            raise ValueError("El código ya fue utilizado.")

        if datetime.utcnow() > registro.expires_at:
            raise ValueError("El código ha expirado. Solicita uno nuevo.")

        registro.attempts += 1
        if registro.attempts > MAX_ATTEMPTS:
            db.session.commit()
            raise ValueError("Demasiados intentos incorrectos. Solicita un nuevo código.")

        if registro.code_hash != cls._hash(code):
            db.session.commit()
            raise ValueError("Código incorrecto.")

        registro.used = True
        db.session.commit()
        return True

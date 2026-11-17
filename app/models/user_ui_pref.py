from app.extensions import db


class UserUiPref(db.Model):
    """Preferencias de interfaz propias de cada usuario (ej. orden de columnas de una grilla).
    Solo afectan la vista de ese usuario."""

    __tablename__ = "user_ui_prefs"
    __table_args__ = (db.UniqueConstraint("user_id", "clave", name="uq_user_ui_pref"),)

    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    clave   = db.Column(db.String(100), nullable=False)
    valor   = db.Column(db.Text, nullable=False, default="null")

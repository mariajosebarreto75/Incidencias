from datetime import datetime
from app.extensions import db


class HeAuditLog(db.Model):
    __tablename__ = "he_audit_log"

    id           = db.Column(db.Integer, primary_key=True)
    operacion    = db.Column(db.String(20), nullable=False)   # INSERT / UPDATE / DELETE
    registro_id  = db.Column(db.Integer)                       # id del registro afectado
    contrato_id  = db.Column(db.Integer)
    contrato_nom = db.Column(db.String(200))
    fecha_labor  = db.Column(db.Date)
    cedula       = db.Column(db.String(50))
    nombre       = db.Column(db.String(200))
    horas_rep    = db.Column(db.Numeric(6, 2))
    id_concepto  = db.Column(db.String(10))
    tipo_he      = db.Column(db.String(200))
    estado_antes = db.Column(db.String(30))
    estado_desp  = db.Column(db.String(30))
    datos_antes  = db.Column(db.Text)   # JSON del registro antes del cambio
    datos_desp   = db.Column(db.Text)   # JSON del registro después del cambio
    usuario_id   = db.Column(db.Integer, db.ForeignKey("users.id"))
    usuario_nom  = db.Column(db.String(200))
    usuario_rol  = db.Column(db.String(50))
    ip           = db.Column(db.String(60))
    fecha        = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    usuario = db.relationship("User", foreign_keys=[usuario_id])

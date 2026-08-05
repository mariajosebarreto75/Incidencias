from datetime import datetime
from app.extensions import db


class HeCorte(db.Model):
    __tablename__ = "he_cortes"

    id              = db.Column(db.Integer, primary_key=True)
    nombre          = db.Column(db.String(100), nullable=False)
    fecha_inicio    = db.Column(db.Date, nullable=False)
    fecha_fin       = db.Column(db.Date, nullable=False)
    estado          = db.Column(db.String(20), default="ABIERTO")   # ABIERTO / CERRADO
    contrato_id     = db.Column(db.Integer, db.ForeignKey("contratos.id"))
    creado_por_id   = db.Column(db.Integer, db.ForeignKey("users.id"))
    cerrado_por_id  = db.Column(db.Integer, db.ForeignKey("users.id"))
    fecha_creacion  = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_cierre    = db.Column(db.DateTime)
    observacion     = db.Column(db.Text)

    contrato    = db.relationship("Contrato", backref="he_cortes")
    creado_por  = db.relationship("User", foreign_keys=[creado_por_id])
    cerrado_por = db.relationship("User", foreign_keys=[cerrado_por_id])

    def to_dict(self):
        return {
            "id":             self.id,
            "nombre":         self.nombre,
            "fecha_inicio":   self.fecha_inicio.isoformat() if self.fecha_inicio else "",
            "fecha_fin":      self.fecha_fin.isoformat() if self.fecha_fin else "",
            "estado":         self.estado,
            "contrato_id":    self.contrato_id,
            "contrato":       self.contrato.contrato if self.contrato else "Todos",
            "creado_por":     self.creado_por.nombre_completo if self.creado_por else "",
            "cerrado_por":    self.cerrado_por.nombre_completo if self.cerrado_por else "",
            "fecha_creacion": self.fecha_creacion.strftime("%Y-%m-%d %H:%M") if self.fecha_creacion else "",
            "fecha_cierre":   self.fecha_cierre.strftime("%Y-%m-%d %H:%M") if self.fecha_cierre else "",
            "observacion":    self.observacion or "",
        }

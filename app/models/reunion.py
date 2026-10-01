from datetime import datetime
from app.extensions import db


class Reunion(db.Model):
    __tablename__ = "reuniones"

    id           = db.Column(db.Integer, primary_key=True)
    titulo       = db.Column(db.String(200), nullable=False)
    descripcion  = db.Column(db.Text)
    participantes= db.Column(db.Text)          # texto libre
    fecha        = db.Column(db.Date, nullable=False)
    hora_inicio  = db.Column(db.String(5), nullable=False)   # "HH:MM"
    hora_fin     = db.Column(db.String(5), nullable=False)
    contrato_id  = db.Column(db.Integer, db.ForeignKey("contratos.id"), nullable=True)
    recurrente   = db.Column(db.Boolean, default=False, nullable=False)
    creado_por   = db.Column(db.String(150))
    created_at   = db.Column(db.DateTime, default=datetime.now)

    contrato = db.relationship("Contrato", backref="reuniones", lazy=True)

    def to_dict(self, fecha_override=None):
        return {
            "id":           self.id,
            "titulo":       self.titulo,
            "descripcion":  self.descripcion or "",
            "participantes":self.participantes or "",
            "fecha":        (fecha_override or self.fecha).isoformat(),
            "hora_inicio":  self.hora_inicio,
            "hora_fin":     self.hora_fin,
            "contrato_id":  self.contrato_id,
            "contrato":     self.contrato.contrato if self.contrato else "",
            "creado_por":   self.creado_por or "",
            "recurrente":   self.recurrente,
        }

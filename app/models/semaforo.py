from datetime import date as _date
from app.extensions import db


class SemaforoCalificacion(db.Model):
    __tablename__ = "semaforo_calificaciones"

    id            = db.Column(db.Integer, primary_key=True)
    fecha         = db.Column(db.Date,    nullable=False, index=True)
    contrato_id   = db.Column(db.Integer, db.ForeignKey("contratos.id"), nullable=False, index=True)

    # Archivos de seguimiento: 1=cumple, 0=no cumple, 3=errores pero cumple
    arch_equipos  = db.Column(db.SmallInteger, nullable=True)   # indisponibilidad equipos
    arch_ingresos = db.Column(db.SmallInteger, nullable=True)   # ingresos
    arch_personas = db.Column(db.SmallInteger, nullable=True)   # indisponibilidad personas
    arch_nota     = db.Column(db.String(300),  nullable=True)   # anotación libre archivos

    # Distribución operativa NEO: hora enviada (ej. "07:30") o texto libre
    distrib_valor = db.Column(db.String(100),  nullable=True)   # "07:30", "no trabaja", "problemas internet", etc.
    distrib_cumple= db.Column(db.SmallInteger, nullable=True)   # 1=cumple, 0=no cumple, null=auto (calculado por hora)
    distrib_nota  = db.Column(db.String(300),  nullable=True)   # anotación libre distribución

    # Horas extras: 1=cumple, 0=no cumple, 3=errores pero cumple
    he_valor      = db.Column(db.SmallInteger, nullable=True)
    he_nota       = db.Column(db.String(300),  nullable=True)

    __table_args__ = (
        db.UniqueConstraint("fecha", "contrato_id", name="uq_semaforo_fecha_contrato"),
    )

    contrato = db.relationship("Contrato", backref="semaforos", lazy="joined")

    def to_dict(self):
        return {
            "id":            self.id,
            "fecha":         str(self.fecha),
            "contrato_id":   self.contrato_id,
            "arch_equipos":  self.arch_equipos,
            "arch_ingresos": self.arch_ingresos,
            "arch_personas": self.arch_personas,
            "arch_nota":     self.arch_nota or "",
            "distrib_valor":  self.distrib_valor or "",
            "distrib_cumple": self.distrib_cumple,
            "distrib_nota":   self.distrib_nota or "",
            "he_valor":       self.he_valor,
            "he_nota":       self.he_nota or "",
        }

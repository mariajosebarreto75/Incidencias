from datetime import datetime
from app.extensions import db


class ParqPago(db.Model):
    __tablename__ = "parq_pagos"

    id              = db.Column(db.Integer, primary_key=True)
    # null si es ingreso ocasional sin cliente registrado
    cliente_id      = db.Column(db.Integer, db.ForeignKey("parq_clientes.id"), nullable=True, index=True)
    concepto        = db.Column(db.String(30), nullable=False)
    # mensualidad | por_horas | por_dia | otro
    mes_pagado      = db.Column(db.String(7))   # AAAA-MM, solo para mensualidades
    valor           = db.Column(db.Numeric(12, 2), nullable=False)
    fecha_pago      = db.Column(db.Date, nullable=False)
    medio           = db.Column(db.String(20), nullable=False)   # efectivo | transferencia
    entidad         = db.Column(db.String(50))                   # Nequi, Daviplata, Bancolombia, otro
    referencia      = db.Column(db.String(100))
    registrado_por  = db.Column(db.String(100))
    creado_en       = db.Column(db.DateTime, default=datetime.now, nullable=False)
    # Borrado lógico
    eliminado       = db.Column(db.Boolean, default=False, nullable=False)
    eliminado_por   = db.Column(db.String(100))
    eliminado_en    = db.Column(db.DateTime)

    cliente = db.relationship("ParqCliente", back_populates="pagos")

    def __repr__(self):
        return f"<ParqPago {self.concepto} ${self.valor} {self.fecha_pago}>"

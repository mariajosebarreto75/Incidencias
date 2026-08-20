from datetime import datetime
from app.extensions import db

CONCEPTOS_HE = {
    "03": "HORA EXTRA DIURNA",
    "04": "HORA EXTRA NOCTURNA",
    "05": "HORA EXTRA DIURNA DOMINICAL O FESTIVA",
    "06": "HORA EXTRA NOCTURNA DOMINICAL O FESTIVA",
    "07": "RECARGO ORDINARIO DOMINICAL Y/O FESTIVO",
    "17": "RECARGO NOCTURNO ORDINARIO",
    "19": "RECARGO DOMINICAL NOCTURNO",
}

FACTOR_HE = {
    "03": 1.25,
    "04": 1.75,
    "05": 2.05,
    "06": 2.55,
    "07": 0.80,
    "17": 0.35,
    "19": 1.15,
}


class HoraExtra(db.Model):
    __tablename__ = "horas_extras"

    id                  = db.Column(db.Integer, primary_key=True)
    contrato_id         = db.Column(db.Integer, db.ForeignKey("contratos.id"), nullable=False)
    fecha_labor         = db.Column(db.Date, nullable=False)
    cedula              = db.Column(db.String(50), nullable=False)
    nombre              = db.Column(db.String(200))
    recurso             = db.Column(db.String(200))
    id_concepto         = db.Column(db.String(10), nullable=False)
    tipo_he             = db.Column(db.String(200))
    horas_reportadas    = db.Column(db.Numeric(6, 2), nullable=False, default=0)
    horas_compensadas   = db.Column(db.Numeric(6, 2), default=0)
    placa               = db.Column(db.String(50))
    hora_inicio         = db.Column(db.String(20))
    hora_fin            = db.Column(db.String(20))
    autorizacion_sup    = db.Column(db.String(200))
    justificacion       = db.Column(db.Text)
    observacion         = db.Column(db.Text)
    valor_hora          = db.Column(db.Numeric(14, 2))
    valor_extra_nomina  = db.Column(db.Numeric(14, 2))
    valor_extra         = db.Column(db.Numeric(14, 2))

    # Validación NEO
    autorizacion_neo    = db.Column(db.String(30))   # CONFORME / NO CONFORME / DESCONTADA
    horas_autorizadas   = db.Column(db.Integer)
    obs_neo             = db.Column(db.Text)
    estado              = db.Column(db.String(30), default="PENDIENTE")  # PENDIENTE / CONFORME / NO CONFORME / DESCONTADA

    corte_id            = db.Column(db.Integer, db.ForeignKey("he_cortes.id"))

    # Metadatos
    reportado_por_id    = db.Column(db.Integer, db.ForeignKey("users.id"))
    fecha_reporte       = db.Column(db.DateTime, default=datetime.utcnow)
    validado_por_id     = db.Column(db.Integer, db.ForeignKey("users.id"))
    fecha_validacion    = db.Column(db.DateTime)

    contrato        = db.relationship("Contrato", backref="horas_extras")
    reportado_por   = db.relationship("User", foreign_keys=[reportado_por_id])
    validado_por    = db.relationship("User", foreign_keys=[validado_por_id])

    def to_dict(self):
        return {
            "id":                 self.id,
            "contrato_id":        self.contrato_id,
            "contrato":           self.contrato.contrato if self.contrato else "",
            "fecha_labor":        self.fecha_labor.isoformat() if self.fecha_labor else "",
            "cedula":             self.cedula,
            "nombre":             self.nombre or "",
            "recurso":            self.recurso or "",
            "id_concepto":        self.id_concepto,
            "tipo_he":            self.tipo_he or "",
            "horas_reportadas":   float(self.horas_reportadas or 0),
            "horas_compensadas":  float(self.horas_compensadas or 0),
            "placa":              self.placa or "",
            "hora_inicio":        self.hora_inicio or "",
            "hora_fin":           self.hora_fin or "",
            "autorizacion_sup":   self.autorizacion_sup or "",
            "justificacion":      self.justificacion or "",
            "observacion":        self.observacion or "",
            "valor_hora":         float(self.valor_hora) if self.valor_hora else None,
            "valor_extra_nomina": float(self.valor_extra_nomina) if self.valor_extra_nomina else None,
            "valor_extra":        float(self.valor_extra) if self.valor_extra else None,
            "autorizacion_neo":   self.autorizacion_neo or "",
            "horas_autorizadas":  int(self.horas_autorizadas) if self.horas_autorizadas is not None else None,
            "obs_neo":            self.obs_neo or "",
            "estado":             self.estado or "PENDIENTE",
            "reportado_por":      self.reportado_por.nombre_completo if self.reportado_por else "",
            "fecha_reporte":      self.fecha_reporte.strftime("%Y-%m-%d %H:%M") if self.fecha_reporte else "",
            "validado_por":       self.validado_por.nombre_completo if self.validado_por else "",
            "fecha_validacion":   self.fecha_validacion.strftime("%Y-%m-%d %H:%M") if self.fecha_validacion else "",
        }

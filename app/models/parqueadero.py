from datetime import datetime
from app.extensions import db


class ParqueaderoRegistro(db.Model):
    __tablename__ = "parqueadero_registros"

    id           = db.Column(db.Integer, primary_key=True)
    placa        = db.Column(db.String(10), nullable=False, index=True)
    tipo         = db.Column(db.String(10), nullable=False)   # 'carro' | 'moto'
    hora_ingreso = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    hora_salida  = db.Column(db.DateTime, nullable=True)
    cascos       = db.Column(db.Integer, default=0, nullable=False)
    valor_total  = db.Column(db.Float, nullable=True)
    estado       = db.Column(db.String(15), nullable=False, default="activo")  # activo | finalizado
    fecha        = db.Column(db.Date, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":           self.id,
            "placa":        self.placa,
            "tipo":         self.tipo,
            "hora_ingreso": self.hora_ingreso.strftime("%Y-%m-%dT%H:%M:%S") if self.hora_ingreso else None,
            "hora_salida":  self.hora_salida.strftime("%Y-%m-%dT%H:%M:%S")  if self.hora_salida  else None,
            "cascos":       self.cascos,
            "valor_total":  self.valor_total,
            "estado":       self.estado,
            "fecha":        self.fecha.isoformat() if self.fecha else None,
        }

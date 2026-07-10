from datetime import datetime
from app.extensions import db


class AlertaGPS(db.Model):

    __tablename__ = "alertas_gps"

    # ── Clave propia ──────────────────────────────────────────
    id = db.Column(db.Integer, primary_key=True)

    # ── ID del lado de GPS Monitor (evita duplicados) ─────────
    alert_id_gps = db.Column(db.Integer, unique=True, nullable=False)

    # ── Datos de la alerta ────────────────────────────────────
    alert_type   = db.Column(db.String(80))      # speed_infraction, unscheduled_stop, etc.
    triggered_at = db.Column(db.String(50))       # fecha/hora UTC que dio GPS Monitor
    vehicle_plate= db.Column(db.String(20))
    lat          = db.Column(db.Float)
    lon          = db.Column(db.Float)
    metadata_raw = db.Column(db.Text)            # JSON string con metadata adicional

    # ── Datos del plan del día ────────────────────────────────
    contract_code  = db.Column(db.String(50))    # "021E", "2876" — clave para filtrar por coordinador
    contract_group = db.Column(db.String(10))
    resource_code  = db.Column(db.String(50))
    brigade_type   = db.Column(db.String(50))
    plan_date      = db.Column(db.String(20))
    tech1_doc      = db.Column(db.BigInteger)
    tech2_doc      = db.Column(db.BigInteger)
    tech3_doc      = db.Column(db.BigInteger)
    tech4_doc      = db.Column(db.BigInteger)
    tech5_doc      = db.Column(db.BigInteger)

    # ── Datos de OT (solo execution_overtime) ─────────────────
    order_number      = db.Column(db.String(50))
    order_type        = db.Column(db.String(100))
    item_duration_min = db.Column(db.Integer)

    # ── Estado en TU sistema ──────────────────────────────────
    # "pendiente" → recién llegó, nadie la ha visto
    # "resuelta"  → coordinador la marcó como resuelta (se envió "resolver" a GPS Monitor)
    # "liberada"  → coordinador la liberó (se envió "liberar" a GPS Monitor)
    estado_local  = db.Column(db.String(20), default="pendiente", nullable=False)
    atendida_por  = db.Column(db.String(100))    # username del coordinador que respondió
    fecha_atencion= db.Column(db.DateTime)

    # ── Cuándo la recibimos nosotros ──────────────────────────
    fecha_recibida = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AlertaGPS {self.alert_id_gps} {self.alert_type} {self.vehicle_plate}>"

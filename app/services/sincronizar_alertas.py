"""
sincronizar_alertas.py

Llama a GPS Monitor, toma las alertas nuevas y las guarda en la BD.
Solo inserta las que aún no existen (por alert_id_gps único).
"""

import json
from datetime import datetime

from app.extensions import db
from app.models.alerta_gps import AlertaGPS
from app.services.gps_monitor import obtener_alertas_pendientes


def sincronizar():
    """
    Descarga alertas pendientes de GPS Monitor y guarda las nuevas en la BD.
    Devuelve (insertadas, ya_existian) para logging.
    """
    try:
        alertas = obtener_alertas_pendientes()
    except Exception as e:
        print(f"[GPS Monitor] Error al consultar alertas: {e}")
        return 0, 0

    insertadas  = 0
    ya_existian = 0

    # Carga todos los IDs ya guardados en un set — evita queries dentro del loop
    # y por tanto evita el autoflush de SQLAlchemy que causaba UniqueViolation.
    ids_api = {a["id"] for a in alertas}
    ids_existentes = {
        row[0] for row in
        db.session.query(AlertaGPS.alert_id_gps)
                  .filter(AlertaGPS.alert_id_gps.in_(ids_api))
                  .all()
    }

    for a in alertas:
        if a["id"] in ids_existentes:
            ya_existian += 1
            continue

        nueva = AlertaGPS(
            alert_id_gps   = a["id"],
            alert_type     = a.get("alert_type"),
            triggered_at   = a.get("triggered_at"),
            vehicle_plate  = a.get("vehicle_plate"),
            lat            = a.get("lat"),
            lon            = a.get("lon"),
            metadata_raw   = json.dumps(a.get("metadata")) if a.get("metadata") else None,

            # Plan del día
            contract_code  = a.get("contract_code"),
            contract_group = a.get("contract_group"),
            resource_code  = a.get("resource_code"),
            brigade_type   = a.get("brigade_type"),
            plan_date      = a.get("plan_date"),
            tech1_doc      = a.get("tech1_doc"),
            tech2_doc      = a.get("tech2_doc"),
            tech3_doc      = a.get("tech3_doc"),
            tech4_doc      = a.get("tech4_doc"),
            tech5_doc      = a.get("tech5_doc"),

            # OT (solo execution_overtime)
            order_number      = a.get("order_number"),
            order_type        = a.get("order_type"),
            item_duration_min = a.get("item_duration_min"),

            estado_local   = "pendiente",
            fecha_recibida = datetime.utcnow(),
        )
        db.session.add(nueva)
        ids_existentes.add(a["id"])  # evita duplicados dentro del mismo lote
        insertadas += 1

    if insertadas:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[GPS Monitor] Error al guardar alertas: {e}")
            return 0, 0

    print(f"[GPS Monitor] Sync: {insertadas} nuevas, {ya_existian} ya existían")
    return insertadas, ya_existian

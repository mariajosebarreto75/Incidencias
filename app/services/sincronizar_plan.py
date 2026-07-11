"""
sincronizar_plan.py

Descarga el plan del día desde GPS Monitor y lo guarda en distribucion_operativa.
Cada ejecución reemplaza los registros del rango de fechas solicitado
(borra los existentes del rango y reinscerta los nuevos).
"""

from datetime import date, timedelta

from app.extensions import db
from app.models.distribucion_operativa import DistribucionOperativa
from app.services.gps_monitor import obtener_plan_del_dia


def sincronizar_plan(from_date=None, to_date=None):
    """
    Sincroniza el plan operativo de GPS Monitor → distribucion_operativa.

    - from_date: fecha inicio (str "YYYY-MM-DD" o date). Default: hoy.
    - to_date:   fecha fin   (str "YYYY-MM-DD" o date). Default: igual a from_date.

    Devuelve dict con: {"insertados": N, "eliminados": N, "fecha_desde": ..., "fecha_hasta": ...}
    """
    from datetime import datetime

    def _to_date(d):
        if d is None:
            return date.today()
        if isinstance(d, date):
            return d
        return datetime.strptime(d, "%Y-%m-%d").date()

    fd = _to_date(from_date)
    ft = _to_date(to_date) if to_date is not None else fd

    try:
        items = obtener_plan_del_dia(fd.isoformat(), ft.isoformat())
    except Exception as e:
        print(f"[Plan GPS] Error al consultar API: {e}")
        return {"error": str(e)}

    if not items:
        print(f"[Plan GPS] Sin datos para {fd} → {ft}")
        return {"insertados": 0, "eliminados": 0,
                "fecha_desde": fd.isoformat(), "fecha_hasta": ft.isoformat()}

    # Determinar las fechas reales presentes en la respuesta
    fechas_en_datos = set()
    for item in items:
        pd_str = item.get("plan_date")
        if pd_str:
            try:
                fechas_en_datos.add(datetime.strptime(str(pd_str)[:10], "%Y-%m-%d").date())
            except ValueError:
                pass

    # Eliminar registros existentes solo en esas fechas (origen = GPS Monitor)
    eliminados = 0
    if fechas_en_datos:
        eliminados = (
            DistribucionOperativa.query
            .filter(
                DistribucionOperativa.fecha.in_(list(fechas_en_datos)),
                DistribucionOperativa.origen == "gps_monitor"
            )
            .delete(synchronize_session=False)
        )

    # Insertar nuevos registros
    insertados = 0
    for item in items:
        pd_str = item.get("plan_date")
        if not pd_str:
            continue
        try:
            fecha_plan = datetime.strptime(str(pd_str)[:10], "%Y-%m-%d").date()
        except ValueError:
            continue

        registro = DistribucionOperativa(
            fecha           = fecha_plan,
            contrato        = item.get("contract_code")  or "—",
            recurso         = item.get("resource_code")  or item.get("plate") or "—",
            placa           = item.get("plate"),
            orden_trabajo   = item.get("order_number"),
            tipo_actividad  = item.get("order_type"),
            tipo_cuadrilla  = item.get("brigade_type"),
            cedula_1        = str(item["tech1_doc"]) if item.get("tech1_doc") else None,
            cedula_2        = str(item["tech2_doc"]) if item.get("tech2_doc") else None,
            cedula_3        = str(item["tech3_doc"]) if item.get("tech3_doc") else None,
            cedula_4        = str(item["tech4_doc"]) if item.get("tech4_doc") else None,
            cedula_5        = str(item["tech5_doc"]) if item.get("tech5_doc") else None,
            latitud         = str(item["client_lat"]) if item.get("client_lat") else None,
            longitud        = str(item["client_lon"]) if item.get("client_lon") else None,
            duracion_actividad = str(item["duration_min"]) if item.get("duration_min") else None,
            observacion     = item.get("observation"),
            origen          = "gps_monitor",
        )
        db.session.add(registro)
        insertados += 1

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[Plan GPS] Error al guardar: {e}")
        return {"error": str(e)}

    print(f"[Plan GPS] Sync {fd}→{ft}: {eliminados} eliminados, {insertados} insertados")
    return {
        "insertados":   insertados,
        "eliminados":   eliminados,
        "fecha_desde":  fd.isoformat(),
        "fecha_hasta":  ft.isoformat(),
    }

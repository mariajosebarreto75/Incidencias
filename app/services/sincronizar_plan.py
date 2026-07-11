"""
Descarga el plan del día desde GPS Monitor (DataFrame) y lo guarda
en distribucion_operativa. Reemplaza solo los registros de origen=gps_monitor
para el rango de fechas solicitado.
"""

from datetime import date

from app.extensions import db
from app.models.distribucion_operativa import DistribucionOperativa
from app.models.contrato import Contrato
from app.services.gps_monitor import obtener_plan_del_dia


def sincronizar_plan(from_date=None, to_date=None):
    """
    from_date / to_date: str "YYYY-MM-DD" o datetime.date. Default: hoy.
    Devuelve dict: {"insertados", "eliminados", "fecha_desde", "fecha_hasta"}
                o  {"error": "..."}
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

    # ── Llamar la función del desarrollador ──────────────────────────────
    try:
        df = obtener_plan_del_dia(fd.isoformat(), ft.isoformat())
    except Exception as e:
        print(f"[Plan GPS] Error al consultar API: {e}")
        return {"error": str(e)}

    # ── Validar que el DataFrame no esté vacío ───────────────────────────
    if df.empty:
        print(f"[Plan GPS] Sin datos para {fd} → {ft}")
        return {
            "insertados": 0,
            "eliminados": 0,
            "fecha_desde": fd.isoformat(),
            "fecha_hasta": ft.isoformat(),
            "mensaje": "No hay plan cargado en GPS Monitor para ese rango de fechas.",
        }

    # ── Resolver contract_code → nombre completo de contrato ─────────────
    codigos = set(df["contract_code"].dropna().astype(str).unique())
    contratos_db = {
        c.codigo: c.contrato
        for c in Contrato.query.filter(Contrato.codigo.in_(codigos)).all()
    }

    def resolver_contrato(code):
        if not code or str(code) == "nan":
            return "—"
        return contratos_db.get(str(code), str(code))

    # ── Determinar fechas presentes en los datos ──────────────────────────
    fechas = set(df["plan_date"].dropna().unique())

    # ── Eliminar registros existentes de GPS Monitor para esas fechas ─────
    eliminados = 0
    if fechas:
        eliminados = (
            DistribucionOperativa.query
            .filter(
                DistribucionOperativa.fecha.in_(list(fechas)),
                DistribucionOperativa.origen == "gps_monitor",
            )
            .delete(synchronize_session=False)
        )

    # ── Insertar nuevos registros ─────────────────────────────────────────
    def _str(val):
        """Convierte valor del DataFrame a str limpio o None."""
        import pandas as pd
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        s = str(val).strip()
        return s if s and s.lower() != "nan" else None

    insertados = 0
    for _, row in df.iterrows():
        fecha_plan = row.get("plan_date")
        if fecha_plan is None:
            continue

        registro = DistribucionOperativa(
            fecha              = fecha_plan,
            contrato           = resolver_contrato(row.get("contract_code")),
            recurso            = _str(row.get("resource_code")) or _str(row.get("plate")) or "—",
            placa              = _str(row.get("plate")),
            orden_trabajo      = _str(row.get("order_number")),
            tipo_actividad     = _str(row.get("order_type")),
            tipo_cuadrilla     = _str(row.get("brigade_type")),
            cedula_1           = _str(row.get("tech1_doc")),
            cedula_2           = _str(row.get("tech2_doc")),
            cedula_3           = _str(row.get("tech3_doc")),
            cedula_4           = _str(row.get("tech4_doc")),
            cedula_5           = _str(row.get("tech5_doc")),
            latitud            = _str(row.get("client_lat")),
            longitud           = _str(row.get("client_lon")),
            duracion_actividad = _str(row.get("duration_min")),
            observacion        = _str(row.get("observation")),
            origen             = "gps_monitor",
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
        "insertados":  insertados,
        "eliminados":  eliminados,
        "fecha_desde": fd.isoformat(),
        "fecha_hasta": ft.isoformat(),
    }

"""
Descarga el plan del día desde GPS Monitor (DataFrame) y lo guarda
en distribucion_operativa. Reemplaza solo los registros de origen=gps_monitor
para el rango de fechas solicitado.
"""

from datetime import date

from app.extensions import db
from app.models.distribucion_operativa import DistribucionOperativa
from app.models.contrato import Contrato
from app.models.meta_operativa import MetaOperativa
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

    # ── Cargar metas operativas para lookup ─────────────────────────────
    # Estructura: {(contrato, tipo_cuadrilla, proceso): meta}
    #             {(contrato, tipo_cuadrilla, None):    meta}  ← sin proceso
    metas_lookup = {}
    for m in MetaOperativa.query.all():
        key_con_proceso = (m.contrato, m.Tipo_cuadrilla, m.Proceso)
        key_sin_proceso = (m.contrato, m.Tipo_cuadrilla, None)
        metas_lookup[key_con_proceso] = m.Meta_Produccion
        if m.Proceso is None:
            metas_lookup[key_sin_proceso] = m.Meta_Produccion

    def resolver_meta(contrato_nombre, tipo_cuadrilla, tipo_actividad):
        """Busca meta: primero con proceso, luego sin proceso."""
        if not contrato_nombre or not tipo_cuadrilla:
            return None
        # intento 1: contrato + cuadrilla + proceso (tipo_actividad)
        meta = metas_lookup.get((contrato_nombre, tipo_cuadrilla, tipo_actividad))
        if meta is not None:
            return meta
        # intento 2: contrato + cuadrilla sin importar proceso
        meta = metas_lookup.get((contrato_nombre, tipo_cuadrilla, None))
        if meta is not None:
            return meta
        # intento 3: recorrer y buscar cuadrilla que coincida ignorando caso
        tc_lower = tipo_cuadrilla.lower().strip()
        for (c, tc, _), v in metas_lookup.items():
            if c == contrato_nombre and tc and tc.lower().strip() == tc_lower:
                return v
        return None

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
    def _str(val, es_cedula=False):
        """Convierte valor del DataFrame a str limpio o None."""
        import pandas as pd
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        # Cédulas vienen como float (1006323227.0) → convertir a int primero
        if es_cedula:
            try:
                return str(int(float(val)))
            except (ValueError, TypeError):
                return None
        s = str(val).strip()
        return s if s and s.lower() != "nan" else None

    insertados = 0
    for _, row in df.iterrows():
        fecha_plan = row.get("plan_date")
        if fecha_plan is None:
            continue

        contrato_nombre  = resolver_contrato(row.get("contract_code"))
        tipo_cuadrilla_v = _str(row.get("brigade_type"))
        tipo_actividad_v = _str(row.get("order_type"))

        registro = DistribucionOperativa(
            fecha              = fecha_plan,
            contrato           = contrato_nombre,
            recurso            = _str(row.get("resource_code")) or _str(row.get("plate")) or "—",
            placa              = _str(row.get("plate")),
            orden_trabajo      = _str(row.get("order_number")),
            tipo_actividad     = tipo_actividad_v,
            tipo_cuadrilla     = tipo_cuadrilla_v,
            cedula_1           = _str(row.get("tech1_doc"), es_cedula=True),
            cedula_2           = _str(row.get("tech2_doc"), es_cedula=True),
            cedula_3           = _str(row.get("tech3_doc"), es_cedula=True),
            cedula_4           = _str(row.get("tech4_doc"), es_cedula=True),
            cedula_5           = _str(row.get("tech5_doc"), es_cedula=True),
            latitud            = _str(row.get("client_lat")),
            longitud           = _str(row.get("client_lon")),
            duracion_actividad = _str(row.get("duration_min")),
            observacion        = _str(row.get("observation")),
            meta               = resolver_meta(contrato_nombre, tipo_cuadrilla_v, tipo_actividad_v),
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

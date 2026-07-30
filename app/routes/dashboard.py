from flask import (
    Blueprint,
    render_template,
    request,
    abort
)

from flask_login import (
    login_required,
    current_user
)

from sqlalchemy import func

from app.extensions import db
from app.models.contrato import Contrato
from app.models.user_contrato import UserContrato
from app.models.reporte_operacional import ReporteOperacional


dashboard = Blueprint(
    "dashboard",
    __name__
)


# ======================
# DIRECTOR
# ======================

@dashboard.route(
    "/director"
)

@login_required
def director():

    return f"""

    Bienvenido Director:

    {current_user.nombre_completo}

    """


# =====================================
# DASHBOARD GERENCIAL (indicadores)
# =====================================

_TOP_N = 12


def _formato_dias_horas(total_horas):
    """Convierte un total de horas (float) a un texto compacto 'Xd Yh Zm'."""
    total_minutos = round((total_horas or 0) * 60)
    dias, resto = divmod(total_minutos, 24 * 60)
    horas, minutos = divmod(resto, 60)
    if dias > 0:
        return f"{dias}d {horas}h"
    return f"{horas}h {minutos}m"


def _top_n_con_otros(pares, n=_TOP_N):
    """Recibe [(etiqueta, cantidad), ...], devuelve el top-n ordenado desc.
    y agrupa el resto en 'Otros' para no saturar el gráfico."""
    limpio = [(etq if etq else "Sin dato", cnt) for etq, cnt in pares]
    limpio.sort(key=lambda p: p[1], reverse=True)
    top = limpio[:n]
    resto = limpio[n:]
    if resto:
        top.append(("Otros", sum(c for _, c in resto)))
    return top


@dashboard.route("/dashboard-gerencial")
@login_required
def indicadores():

    if not (current_user.rol.lower() in ("admin", "director") or current_user.acceso_dashboard):
        abort(403)

    # Contratos visibles para este usuario (si no tiene asignados, ve todos)
    asignados = UserContrato.query.filter_by(user_id=current_user.id).all()
    contratos_restringidos = [uc.contrato for uc in asignados] if asignados else None

    if contratos_restringidos is not None:
        lista_contratos = sorted(contratos_restringidos)
    else:
        lista_contratos = [
            c.contrato for c in Contrato.query.order_by(Contrato.contrato).all()
        ]

    contrato_filtro = request.args.get("contrato", "").strip()
    if contrato_filtro not in lista_contratos:
        contrato_filtro = ""

    filtros_sql = []
    if contratos_restringidos is not None:
        filtros_sql.append(ReporteOperacional.contrato.in_(contratos_restringidos))
    if contrato_filtro:
        filtros_sql.append(ReporteOperacional.contrato == contrato_filtro)

    def _query():
        q = db.session.query(ReporteOperacional)
        for f in filtros_sql:
            q = q.filter(f)
        return q

    def _contar(*group_cols):
        q = db.session.query(*group_cols, func.count(ReporteOperacional.id))
        for f in filtros_sql:
            q = q.filter(f)
        return q.group_by(*group_cols).all()

    # ---- KPIs ----
    total_reportes = _query().count()
    total_pendientes = _query().filter(ReporteOperacional.estado == "Abierto").count()
    total_conformes = _query().filter(ReporteOperacional.conformidad_neo == "Conforme").count()
    total_no_conformes = _query().filter(ReporteOperacional.conformidad_neo == "No conforme").count()
    total_cerrados = _query().filter(ReporteOperacional.estado == "Cerrado").count()

    suma_horas = (
        db.session.query(func.sum(ReporteOperacional.horas_afectadas))
        .filter(*filtros_sql).scalar()
    ) or 0
    tiempo_desviacion_txt = _formato_dias_horas(suma_horas)

    suma_afectacion = (
        db.session.query(func.sum(ReporteOperacional.afectacion_economica))
        .filter(*filtros_sql).scalar()
    ) or 0

    # ---- Series para gráficos ----
    def _serie(pares):
        datos = _top_n_con_otros(pares)
        maximo = max((c for _, c in datos), default=0)
        return {"datos": datos, "maximo": maximo}

    reportes_por_contrato = _serie(_contar(ReporteOperacional.contrato))
    reportes_por_recurso = _serie(_contar(ReporteOperacional.recurso))
    reportes_por_tipo = _serie(_contar(ReporteOperacional.tipo_incidencia))
    reportes_por_accion = _serie(_contar(ReporteOperacional.accion_a_tomar))

    pendientes_por_contrato = _serie(
        db.session.query(ReporteOperacional.contrato, func.count(ReporteOperacional.id))
        .filter(ReporteOperacional.estado == "Abierto")
        .filter(*filtros_sql)
        .group_by(ReporteOperacional.contrato)
        .all()
    )

    # ---- % de respuesta por contrato ----
    total_por_contrato = dict(_contar(ReporteOperacional.contrato))
    respondido_por_contrato = dict(
        db.session.query(ReporteOperacional.contrato, func.count(ReporteOperacional.id))
        .filter(ReporteOperacional.estado != "Abierto")
        .filter(*filtros_sql)
        .group_by(ReporteOperacional.contrato)
        .all()
    )
    pct_respuesta_datos = []
    for contrato, total in total_por_contrato.items():
        respondidos = respondido_por_contrato.get(contrato, 0)
        pct = round((respondidos / total * 100), 1) if total else 0
        pct_respuesta_datos.append((contrato if contrato else "Sin dato", pct))
    pct_respuesta_datos.sort(key=lambda p: p[1], reverse=True)
    pct_respuesta_por_contrato = {"datos": pct_respuesta_datos}

    # ---- % Conformidad NEO (torta) ----
    total_calificados = total_conformes + total_no_conformes
    pct_conforme = round(total_conformes / total_calificados * 100, 1) if total_calificados else 0
    pct_no_conforme = round(100 - pct_conforme, 1) if total_calificados else 0
    conformidad_pie = {
        "pct_conforme": pct_conforme,
        "pct_no_conforme": pct_no_conforme,
        "grados_conforme": round(pct_conforme * 3.6, 1),
        "total_conformes": total_conformes,
        "total_no_conformes": total_no_conformes,
    }

    # ---- Reportes por día (últimos 30 días con datos) ----
    por_dia_raw = (
        db.session.query(ReporteOperacional.fecha_reporte, func.count(ReporteOperacional.id))
        .filter(*filtros_sql)
        .group_by(ReporteOperacional.fecha_reporte)
        .order_by(ReporteOperacional.fecha_reporte)
        .all()
    )[-30:]
    maximo_dia = max((c for _, c in por_dia_raw), default=0)
    reportes_por_dia = {
        "datos": [(f.strftime("%d/%m") if f else "Sin fecha", c) for f, c in por_dia_raw],
        "maximo": maximo_dia,
    }

    # Nombre completo + rol para el encabezado / link de "volver"
    rol = current_user.rol.lower()
    home_por_rol = {
        "neo":         "neo.home_neo",
        "coordinador": "coordinador.dashboard_coordinador",
        "admin":       "admin_bp.dashboard",
        "director":    "dashboard.director",
    }

    return render_template(
        "dashboard/indicadores.html",
        lista_contratos=lista_contratos,
        contrato_filtro=contrato_filtro,
        kpis={
            "total_reportes":       total_reportes,
            "total_pendientes":     total_pendientes,
            "total_conformes":      total_conformes,
            "total_no_conformes":   total_no_conformes,
            "total_cerrados":       total_cerrados,
            "tiempo_desviacion":    tiempo_desviacion_txt,
            "afectacion_economica": suma_afectacion,
        },
        reportes_por_contrato=reportes_por_contrato,
        pendientes_por_contrato=pendientes_por_contrato,
        reportes_por_recurso=reportes_por_recurso,
        reportes_por_tipo=reportes_por_tipo,
        reportes_por_accion=reportes_por_accion,
        pct_respuesta_por_contrato=pct_respuesta_por_contrato,
        conformidad_pie=conformidad_pie,
        reportes_por_dia=reportes_por_dia,
        home_endpoint=home_por_rol.get(rol),
    )

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

    # ---- Series para gráficos ----
    def _serie(pares):
        datos = _top_n_con_otros(pares)
        maximo = max((c for _, c in datos), default=0)
        return {"datos": datos, "maximo": maximo}

    reportes_por_contrato = _serie(_contar(ReporteOperacional.contrato))
    reportes_por_recurso = _serie(_contar(ReporteOperacional.recurso))
    reportes_por_tipo = _serie(_contar(ReporteOperacional.tipo_incidencia))

    pendientes_por_contrato = _serie(
        db.session.query(ReporteOperacional.contrato, func.count(ReporteOperacional.id))
        .filter(ReporteOperacional.estado == "Abierto")
        .filter(*filtros_sql)
        .group_by(ReporteOperacional.contrato)
        .all()
    )

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
            "total_reportes":     total_reportes,
            "total_pendientes":   total_pendientes,
            "total_conformes":    total_conformes,
            "total_no_conformes": total_no_conformes,
            "total_cerrados":     total_cerrados,
        },
        reportes_por_contrato=reportes_por_contrato,
        pendientes_por_contrato=pendientes_por_contrato,
        reportes_por_recurso=reportes_por_recurso,
        reportes_por_tipo=reportes_por_tipo,
        home_endpoint=home_por_rol.get(rol),
    )

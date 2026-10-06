from datetime import date

from flask import (
    Blueprint,
    url_for,
    redirect,
    render_template,
    abort,
    request,
)

from flask_login import (
    login_required,
    current_user
)

from sqlalchemy import func, extract
from app.extensions import db
from app.models.reporte_operacional import ReporteOperacional
from app.models.hora_extra import HoraExtra
from app.models.compromiso import Compromiso
from app.models.contrato import Contrato
from app.models.user import User


dashboard = Blueprint(
    "dashboard",
    __name__
)


# ======================
# DIRECTOR
# ======================

@dashboard.route("/director")
@login_required
def director():
    return redirect(url_for("coordinador.dashboard_coordinador"))


# ======================
# PORTAL DE GERENCIA
# ======================

@dashboard.route("/dashboard/indicadores")
@login_required
def indicadores():
    """Dashboard gerencial con KPIs en tiempo real."""
    rol = current_user.rol.lower()
    if rol not in ("admin", "gerente") and not current_user.tiene_permiso("indicadores"):
        abort(403)

    hoy = date.today()

    # ── Filtros activos (query params) ──────────────────────────
    f_contrato    = request.args.get("contrato", "").strip()
    f_tipo        = request.args.get("tipo", "").strip()
    f_conformidad = request.args.get("conformidad", "").strip()

    def base_q():
        q = ReporteOperacional.query
        if f_contrato:
            q = q.filter(ReporteOperacional.contrato == f_contrato)
        if f_tipo:
            q = q.filter(ReporteOperacional.tipo_incidencia == f_tipo)
        if f_conformidad:
            q = q.filter(ReporteOperacional.conformidad_neo == f_conformidad)
        return q

    def base_agg():
        q = db.session.query
        filters = []
        if f_contrato:
            filters.append(ReporteOperacional.contrato == f_contrato)
        if f_tipo:
            filters.append(ReporteOperacional.tipo_incidencia == f_tipo)
        if f_conformidad:
            filters.append(ReporteOperacional.conformidad_neo == f_conformidad)
        return filters

    # ── Reportes operacionales ──────────────────────────────────
    extra = base_agg()
    neo_total       = base_q().count()
    neo_abiertos    = base_q().filter_by(estado="Abierto").count()
    neo_respondidos = base_q().filter_by(estado="Respondido").count()
    neo_cerrados    = base_q().filter_by(estado="Cerrado").count()
    neo_conformes   = base_q().filter_by(conformidad_neo="Conforme").count()
    neo_no_conf     = base_q().filter_by(conformidad_neo="No conforme").count()
    neo_hoy         = base_q().filter_by(fecha_reporte=hoy).count()

    # ── Horas extras (sin filtros de NEO, son datos independientes) ──
    he_total     = HoraExtra.query.count()
    he_pendiente = HoraExtra.query.filter_by(estado="PENDIENTE").count()
    he_conforme  = HoraExtra.query.filter_by(estado="CONFORME").count()
    he_no_conf   = HoraExtra.query.filter_by(estado="NO CONFORME").count()
    he_hrs_rep   = db.session.query(func.sum(HoraExtra.horas_reportadas)).scalar() or 0
    he_hrs_auth  = db.session.query(func.sum(HoraExtra.horas_autorizadas)).filter(
        HoraExtra.estado.in_(["CONFORME", "DESCONTADA"])
    ).scalar() or 0

    # ── General ────────────────────────────────────────────────
    contratos_activos = Contrato.query.filter_by(activo=True).count()
    usuarios_activos  = User.query.filter_by(activo=True).count()

    # ── Lista de contratos para el filtro (sin aplicar filtro de contrato) ──
    todos_contratos_rows = db.session.query(
        ReporteOperacional.contrato
    ).group_by(ReporteOperacional.contrato)\
     .order_by(ReporteOperacional.contrato).all()
    todos_contratos = [r.contrato for r in todos_contratos_rows]

    # ── Lista de tipos para el filtro (sin aplicar filtro de tipo) ──
    todos_tipos_rows = db.session.query(
        ReporteOperacional.tipo_incidencia
    ).group_by(ReporteOperacional.tipo_incidencia)\
     .order_by(ReporteOperacional.tipo_incidencia).all()
    todos_tipos = [r.tipo_incidencia for r in todos_tipos_rows]

    # ── Por contrato (top 10 por horas afectadas) ─────────────────
    ctr_q = db.session.query(
        ReporteOperacional.contrato,
        func.count(ReporteOperacional.id).label("casos"),
        func.sum(ReporteOperacional.horas_afectadas).label("horas"),
        func.sum(ReporteOperacional.afectacion_economica).label("afectacion"),
    )
    if extra:
        ctr_q = ctr_q.filter(*extra)
    contratos_rows = ctr_q.group_by(ReporteOperacional.contrato)\
        .order_by(func.sum(ReporteOperacional.horas_afectadas).desc())\
        .limit(10).all()

    contratos_data = [
        {
            "contrato": r.contrato,
            "casos": r.casos,
            "horas": round(float(r.horas or 0), 1),
            "afectacion": int(r.afectacion or 0),
        }
        for r in contratos_rows
    ]

    # ── Por tipo de incidencia ────────────────────────────────────
    tip_q = db.session.query(
        ReporteOperacional.tipo_incidencia,
        func.count(ReporteOperacional.id).label("casos"),
        func.sum(ReporteOperacional.horas_afectadas).label("horas"),
        func.sum(ReporteOperacional.afectacion_economica).label("afectacion"),
    )
    if extra:
        tip_q = tip_q.filter(*extra)
    tipos_rows = tip_q.group_by(ReporteOperacional.tipo_incidencia)\
        .order_by(func.count(ReporteOperacional.id).desc()).all()

    tipos_data = [
        {
            "tipo": r.tipo_incidencia,
            "casos": r.casos,
            "horas": round(float(r.horas or 0), 1),
            "afectacion": int(r.afectacion or 0),
        }
        for r in tipos_rows
    ]

    # ── Por acción tomada ─────────────────────────────────────────
    acc_q = db.session.query(
        ReporteOperacional.accion_a_tomar,
        func.count(ReporteOperacional.id).label("casos"),
    ).filter(ReporteOperacional.accion_a_tomar.isnot(None),
             ReporteOperacional.accion_a_tomar != "")
    if extra:
        acc_q = acc_q.filter(*extra)
    acciones_rows = acc_q.group_by(ReporteOperacional.accion_a_tomar)\
        .order_by(func.count(ReporteOperacional.id).desc()).all()

    acciones_data = [
        {"accion": r.accion_a_tomar, "casos": r.casos}
        for r in acciones_rows
    ]

    # ── Evolución mensual ─────────────────────────────────────────
    evo_q = db.session.query(
        extract("year", ReporteOperacional.fecha_reporte).label("anio"),
        extract("month", ReporteOperacional.fecha_reporte).label("mes"),
        func.count(ReporteOperacional.id).label("casos"),
        func.sum(ReporteOperacional.horas_afectadas).label("horas"),
        func.sum(ReporteOperacional.afectacion_economica).label("afectacion"),
    )
    if extra:
        evo_q = evo_q.filter(*extra)
    evolucion_rows = evo_q.group_by("anio", "mes").order_by("anio", "mes").all()

    meses_es = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun",
                "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    evolucion_data = [
        {
            "label": f"{meses_es[int(r.mes)]} {int(r.anio)}",
            "casos": r.casos,
            "horas": round(float(r.horas or 0), 1),
            "afectacion": int(r.afectacion or 0),
        }
        for r in evolucion_rows
    ]

    # ── Tabla de reportes detallada (aplica filtros) ──────────────
    reportes_rows = base_q()\
        .order_by(ReporteOperacional.fecha_reporte.desc(), ReporteOperacional.id.desc())\
        .limit(200).all()

    casos_atencion = [
        {
            "id": r.id,
            "contrato": r.contrato,
            "fecha": r.fecha_reporte.strftime("%d/%m/%Y") if r.fecha_reporte else "",
            "recurso": r.recurso or "—",
            "tipo": r.tipo_incidencia,
            "duracion": r.duracion or "—",
            "observacion": (r.observacion or "")[:120],
            "accion": r.accion_a_tomar or "—",
            "respuesta": (r.respuesta or "")[:100],
            "conformidad": r.conformidad_neo or "—",
            "obs_conf": (r.observacion_conformidad or "")[:100],
            "reportado_por": r.reportado_por or "—",
            "respondido_por": r.respondido_por or "—",
            "estado": r.estado,
            "horas": round(r.horas_afectadas or 0, 1),
            "afectacion": int(r.afectacion_economica or 0),
        }
        for r in reportes_rows
    ]

    # ── Recursos más reincidentes (top 8) ─────────────────────────
    rein_q = db.session.query(
        ReporteOperacional.recurso,
        func.count(ReporteOperacional.id).label("casos"),
        func.sum(ReporteOperacional.horas_afectadas).label("horas"),
    )
    if extra:
        rein_q = rein_q.filter(*extra)
    rein_rows = rein_q.filter(
        ReporteOperacional.recurso.isnot(None),
        ReporteOperacional.recurso != "",
    ).group_by(ReporteOperacional.recurso)\
     .order_by(func.count(ReporteOperacional.id).desc())\
     .limit(8).all()

    reincidentes = [
        {"recurso": r.recurso, "casos": r.casos, "horas": round(float(r.horas or 0), 1)}
        for r in rein_rows
    ]

    stats = {
        "neo": {
            "total": neo_total, "abiertos": neo_abiertos,
            "con_respuesta": neo_respondidos, "cerrados": neo_cerrados,
            "conformes": neo_conformes, "no_conformes": neo_no_conf,
            "hoy": neo_hoy,
            "pct_conf": round(neo_conformes / neo_total * 100, 1) if neo_total else 0,
            "pct_no_conf": round(neo_no_conf / neo_total * 100, 1) if neo_total else 0,
        },
        "he": {
            "total": he_total, "pendiente": he_pendiente,
            "conforme": he_conforme, "no_conforme": he_no_conf,
            "hrs_reportadas": round(he_hrs_rep, 1),
            "hrs_autorizadas": round(he_hrs_auth, 1),
        },
        "general": {
            "contratos": contratos_activos,
            "usuarios": usuarios_activos,
            "hoy": hoy.strftime("%d/%m/%Y"),
        },
    }

    filtros_activos = {
        "contrato": f_contrato,
        "tipo": f_tipo,
        "conformidad": f_conformidad,
        "count": sum(1 for v in [f_contrato, f_tipo, f_conformidad] if v),
    }

    return render_template(
        "dashboard/indicadores.html",
        stats=stats,
        todos_contratos=todos_contratos,
        todos_tipos=todos_tipos,
        contratos_data=contratos_data,
        tipos_data=tipos_data,
        acciones_data=acciones_data,
        evolucion_data=evolucion_data,
        casos_atencion=casos_atencion,
        reincidentes=reincidentes,
        filtros_activos=filtros_activos,
    )


@dashboard.route("/dashboard/hub")
@login_required
def dashboards_hub():
    """Portal de inicio del rol gerente (vista ejecutiva de solo lectura)."""
    groups = [
        {
            "name": "Dashboards Ejecutivos", "icon": "bi-bar-chart-line-fill", "tint": "#0891B2",
            "links": [
                {"label": "Indicadores Gerenciales", "icon": "bi-speedometer2", "url": url_for("dashboard.indicadores"),
                 "desc": "KPIs en tiempo real: reportes, horas extras y compromisos"},
                {"label": "Dashboard HE", "icon": "bi-clock-history", "url": url_for("he_bp.he_dashboard"),
                 "desc": "KPIs de horas extras, tipos de HE, límite legal y valor de nómina"},
                {"label": "Preoperacionales", "icon": "bi-truck", "url": url_for("coordinador.preoperacionales"),
                 "desc": "Estado de inspecciones preoperacionales por sede y contrato"},
            ],
        },
        {
            "name": "Compromisos", "icon": "bi-calendar-check", "tint": "#D97706",
            "links": [
                {"label": "Reuniones", "icon": "bi-calendar3", "url": url_for("compromisos.reuniones"),
                 "desc": "Programación de reuniones por contrato"},
                {"label": "Checklist", "icon": "bi-list-check", "url": url_for("compromisos.checklist"),
                 "desc": "Checklist de reuniones realizadas"},
                {"label": "Agenda", "icon": "bi-journal-check", "url": url_for("compromisos.lista"),
                 "desc": "Compromisos pendientes y atrasados"},
            ],
        },
    ]
    return render_template(
        "portal/home.html",
        page_title="Gerencia",
        page_desc="Portal ejecutivo de gerencia",
        intro_title=f"Hola, {current_user.nombre_completo}",
        intro_sub="Elige un dashboard o módulo para continuar",
        groups=groups,
        home_endpoint=None,
    )

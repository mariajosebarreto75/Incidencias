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

from sqlalchemy import func, extract, case
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
    u = current_user
    if u.rol.lower() not in ("director", "admin"):
        abort(403)
    es_admin = u.rol.lower() == "admin"
    groups = []

    rep_items = []
    if es_admin or u.tiene_permiso("neo_reportes"):
        rep_items.append({"label": "Panel de Reportes NEO", "icon": "bi-clipboard-data-fill",
                           "url": url_for("coordinador.panel_reportes"),
                           "desc": "Valide y gestione reportes operacionales"})
        rep_items.append({"label": "Distribución Operativa", "icon": "bi-diagram-3-fill",
                           "url": url_for("coordinador.distribucion_operativa"),
                           "desc": "Recursos, cuadrillas y órdenes de trabajo"})
    if u.tiene_permiso("indicadores") or es_admin:
        rep_items.append({"label": "Indicadores", "icon": "bi-speedometer2",
                           "url": url_for("dashboard.indicadores"),
                           "desc": "Dashboard gerencial de KPIs en tiempo real"})
    if rep_items:
        groups.append({"name": "Reportar y Operación", "icon": "bi-broadcast-pin",
                        "tint": "#0891B2", "links": rep_items})

    he_items = []
    if es_admin or u.tiene_permiso("horas_extras"):
        he_items.append({"label": "Registro / Validación", "icon": "bi-pencil-square",
                          "url": "/horas-extras", "desc": "Ingreso y validación de horas extras"})
    if es_admin or u.tiene_permiso("dashboard_he"):
        he_items.append({"label": "Dashboard HE", "icon": "bi-bar-chart-line-fill",
                          "url": url_for("he_bp.he_dashboard"),
                          "desc": "KPIs, tipos de HE, límite legal y valor de nómina"})
    if he_items:
        groups.append({"name": "Horas Extras", "icon": "bi-clock-history",
                        "tint": "#8B5CF6", "links": he_items})

    seg_items = []
    if u.tiene_permiso("bi_seguimiento"):
        seg_items.append({"label": "Archivo de Seguimiento", "icon": "bi-folder2-open",
                           "url": url_for("coordinador.bi_seguimiento"),
                           "desc": "Informe operacional de seguimiento (Power BI)"})
    if u.tiene_permiso("bi_inspecciones"):
        seg_items.append({"label": "Inspecciones", "icon": "bi-search",
                           "url": "https://app.powerbi.com/view?r=eyJrIjoiYWYwYmRhZWQtOWYzNC00OWYxLWJkM2MtZGU5ZTk5MDU4ZTMxIiwidCI6ImU1NjkzYWJkLWViMTEtNDk5Mi05OGE5LThhNjRhODJkNTRhYiJ9",
                           "ext": True, "desc": "Indicador de inspecciones (Power BI)"})
    if u.tiene_permiso("preoperacionales") or u.tiene_permiso("preoperacionales_dashboard") or es_admin:
        seg_items.append({"label": "Preoperacionales", "icon": "bi-clipboard-check-fill",
                           "url": url_for("coordinador.preoperacionales"),
                           "desc": "Cumplimiento, estado de vehículos y placas"})
    if es_admin or u.tiene_permiso("semaforo"):
        seg_items.append({"label": "Semáforo (calificar)", "icon": "bi-stoplights-fill",
                           "url": url_for("coordinador.semaforo_dashboard"),
                           "desc": "Registra calificaciones de actividades por contrato"})
    if u.tiene_permiso("semaforo_dashboard"):
        seg_items.append({"label": "Semáforo Dashboard", "icon": "bi-bar-chart-steps",
                           "url": url_for("coordinador.semaforo_dashboard"),
                           "desc": "Visualiza el estado del semáforo sin calificar"})
    if seg_items:
        groups.append({"name": "Seguimiento y Calidad", "icon": "bi-clipboard2-data",
                        "tint": "#16A34A", "links": seg_items})

    groups.append({
        "name": "Compromisos", "icon": "bi-calendar-check", "tint": "#D97706",
        "links": [
            {"label": "Reuniones", "icon": "bi-calendar3", "url": url_for("compromisos.reuniones"),
             "desc": "Programación de reuniones por contrato"},
            {"label": "Checklist", "icon": "bi-list-check", "url": url_for("compromisos.checklist"),
             "desc": "Checklist de reuniones realizadas"},
            {"label": "Agenda", "icon": "bi-journal-check", "url": url_for("compromisos.lista"),
             "desc": "Compromisos pendientes y atrasados"},
        ],
    })

    if es_admin or u.tiene_permiso("gps"):
        groups.append({"name": "GPS", "icon": "bi-geo-alt-fill", "tint": "#DC2626",
                        "links": [{"label": "Rastrear", "icon": "bi-map",
                                   "url": "https://plataforma.sistemagps.online/ui/map/objects",
                                   "ext": True, "desc": "Mapa de vehículos en vivo"}]})

    return render_template(
        "portal/home.html",
        page_title="Director",
        page_desc="Panel directivo — supervisión estratégica y operativa",
        intro_title=f"Hola, {u.nombre_completo}",
        intro_sub="Panel de Director — módulos disponibles según permisos",
        groups=groups,
        home_endpoint=None,
    )


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
    f_recurso     = request.args.get("recurso", "").strip()
    f_anio        = request.args.get("anio", "").strip()
    f_mes         = request.args.get("mes", "").strip()
    # Días: uno o varios separados por coma ("3,7,15")
    f_dias        = sorted({int(d) for d in request.args.get("dia", "").split(",")
                            if d.strip().isdigit() and 1 <= int(d) <= 31})
    f_dia         = ",".join(str(d) for d in f_dias)
    # Semana del mes en bloques de 7 días: 1 = 1-7, 2 = 8-14, ... 5 = 29-fin de mes
    f_semana      = request.args.get("semana", "").strip()
    if f_semana not in ("1", "2", "3", "4", "5"):
        f_semana = ""

    def base_q():
        return ReporteOperacional.query.filter(*base_agg())

    def base_agg():
        # devuelve lista de condiciones para queries con db.session.query(...)
        conds = []
        if f_contrato:
            conds.append(ReporteOperacional.contrato == f_contrato)
        if f_tipo:
            conds.append(ReporteOperacional.tipo_incidencia == f_tipo)
        if f_conformidad:
            conds.append(ReporteOperacional.conformidad_neo == f_conformidad)
        if f_recurso:
            conds.append(ReporteOperacional.recurso == f_recurso)
        if f_anio:
            conds.append(extract("year", ReporteOperacional.fecha_reporte) == int(f_anio))
        if f_mes:
            conds.append(extract("month", ReporteOperacional.fecha_reporte) == int(f_mes))
        dia_col = extract("day", ReporteOperacional.fecha_reporte)
        if f_semana:
            ini = (int(f_semana) - 1) * 7 + 1
            conds.append(dia_col.between(ini, ini + 6))
        if f_dias:
            conds.append(dia_col.in_(f_dias))
        return conds

    # ── Reportes operacionales — una sola query con CASE/WHEN ──────
    extra = base_agg()
    _neo_row = db.session.query(
        func.count(ReporteOperacional.id).label("total"),
        func.sum(func.cast(ReporteOperacional.estado == "Abierto",    db.Integer)).label("abiertos"),
        func.sum(func.cast(ReporteOperacional.estado == "Respondido", db.Integer)).label("respondidos"),
        func.sum(func.cast(ReporteOperacional.estado == "Cerrado",    db.Integer)).label("cerrados"),
        func.sum(func.cast(ReporteOperacional.conformidad_neo == "Conforme",    db.Integer)).label("conformes"),
        func.sum(func.cast(ReporteOperacional.conformidad_neo == "No conforme", db.Integer)).label("no_conf"),
        func.sum(func.cast(ReporteOperacional.fecha_reporte == hoy,   db.Integer)).label("hoy"),
    ).filter(*extra).one()
    neo_total       = _neo_row.total       or 0
    neo_abiertos    = _neo_row.abiertos    or 0
    neo_respondidos = _neo_row.respondidos or 0
    neo_cerrados    = _neo_row.cerrados    or 0
    neo_conformes   = _neo_row.conformes   or 0
    neo_no_conf     = _neo_row.no_conf     or 0
    neo_hoy         = _neo_row.hoy         or 0

    # ── Horas extras — una sola query ────────────────────────────
    _he_row = db.session.query(
        func.count(HoraExtra.id).label("total"),
        func.sum(func.cast(HoraExtra.estado == "PENDIENTE",  db.Integer)).label("pendiente"),
        func.sum(func.cast(HoraExtra.estado == "CONFORME",   db.Integer)).label("conforme"),
        func.sum(func.cast(HoraExtra.estado == "NO CONFORME",db.Integer)).label("no_conf"),
        func.sum(HoraExtra.horas_reportadas).label("hrs_rep"),
        func.sum(
            case((HoraExtra.estado.in_(["CONFORME", "DESCONTADA"]), HoraExtra.horas_autorizadas), else_=0)
        ).label("hrs_auth"),
    ).one()
    he_total     = _he_row.total     or 0
    he_pendiente = _he_row.pendiente or 0
    he_conforme  = _he_row.conforme  or 0
    he_no_conf   = _he_row.no_conf   or 0
    he_hrs_rep   = float(_he_row.hrs_rep  or 0)
    he_hrs_auth  = float(_he_row.hrs_auth or 0)

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

    # ── Lista de recursos para el filtro (top 60 por frecuencia, del contrato elegido) ──
    rec_q = db.session.query(
        ReporteOperacional.recurso,
        func.count(ReporteOperacional.id).label("n"),
    ).filter(ReporteOperacional.recurso.isnot(None), ReporteOperacional.recurso != "")
    if f_contrato:
        rec_q = rec_q.filter(ReporteOperacional.contrato == f_contrato)
    todos_recursos_rows = rec_q.group_by(ReporteOperacional.recurso)\
     .order_by(func.count(ReporteOperacional.id).desc())\
     .limit(60).all()
    todos_recursos = [r.recurso for r in todos_recursos_rows]
    if f_recurso and f_recurso not in todos_recursos:
        todos_recursos.append(f_recurso)

    # ── Fechas disponibles para cascada año→mes→día ───────────────
    fechas_rows = db.session.query(
        extract("year",  ReporteOperacional.fecha_reporte).label("y"),
        extract("month", ReporteOperacional.fecha_reporte).label("m"),
        extract("day",   ReporteOperacional.fecha_reporte).label("d"),
    ).group_by("y", "m", "d").order_by("y", "m", "d").all()

    # estructura: { "2025": { "1": [1,2,3,...], "2": [...] }, ... }
    from collections import defaultdict
    _fd: dict = defaultdict(lambda: defaultdict(list))
    for r in fechas_rows:
        _fd[str(int(r.y))][str(int(r.m))].append(int(r.d))
    fechas_disponibles = {y: dict(meses) for y, meses in _fd.items()}
    anios_disponibles = sorted(fechas_disponibles.keys(), reverse=True)

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

    # ── Acciones a tomar: casos por contrato × recurso × acción ──
    # El front arma las vistas (por contrato, por recurso o ambas anidadas)
    acc_det_q = db.session.query(
        ReporteOperacional.contrato,
        ReporteOperacional.recurso,
        ReporteOperacional.accion_a_tomar,
        func.count(ReporteOperacional.id).label("casos"),
    )
    if extra:
        acc_det_q = acc_det_q.filter(*extra)
    acciones_por = [
        {
            "c": r.contrato or "—",
            "r": r.recurso or "—",
            "a": r.accion_a_tomar or "Sin acción",
            "n": r.casos,
        }
        for r in acc_det_q.group_by(
            ReporteOperacional.contrato,
            ReporteOperacional.recurso,
            ReporteOperacional.accion_a_tomar,
        ).all()
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
            "placa": r.placa or "—",
            "tipo_cuadrilla": r.tipo_cuadrilla or "—",
            "tipo": r.tipo_incidencia,
            "parametro_neo": r.parametro_neo or "—",
            "hora_inicio": r.hora_inicio.strftime("%H:%M") if r.hora_inicio else "—",
            "hora_fin": r.hora_fin.strftime("%H:%M") if r.hora_fin else "—",
            "duracion": r.duracion or "—",
            "horas": round(r.horas_afectadas or 0, 1),
            "afectacion": int(r.afectacion_economica or 0),
            "observacion": r.observacion or "",
            "accion": r.accion_a_tomar or "—",
            "parametro_coordinador": r.parametro_coordinador or "—",
            "respuesta": r.respuesta or "",
            "respondido_por": r.respondido_por or "—",
            "fecha_respuesta": r.fecha_respuesta.strftime("%d/%m/%Y %H:%M") if r.fecha_respuesta else "—",
            "conformidad": r.conformidad_neo or "—",
            "obs_conf": r.observacion_conformidad or "",
            "reportado_por": r.reportado_por or "—",
            "estado": r.estado,
            "orden_trabajo": r.orden_trabajo or "—",
            # Evidencias del reporte (quien reporta)
            "evidencia_1": r.evidencia_1 or "",
            "evidencia_2": r.evidencia_2 or "",
            # Evidencias del coordinador (quien responde)
            "evidencia_coor_1": r.evidencia_coor_1 or "",
            "evidencia_coor_2": r.evidencia_coor_2 or "",
            # Evidencia de conformidad NEO
            "evidencia_conformidad": r.evidencia_conformidad or "",
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
        "recurso": f_recurso,
        "anio": f_anio,
        "mes": f_mes,
        "dia": f_dia,
        "dias": f_dias,
        "semana": f_semana,
        "count": sum(1 for v in [f_contrato, f_tipo, f_conformidad, f_recurso, f_anio, f_mes, f_dia, f_semana] if v),
    }

    return render_template(
        "dashboard/indicadores.html",
        stats=stats,
        todos_contratos=todos_contratos,
        todos_tipos=todos_tipos,
        todos_recursos=todos_recursos,
        contratos_data=contratos_data,
        tipos_data=tipos_data,
        acciones_data=acciones_data,
        acciones_por=acciones_por,
        evolucion_data=evolucion_data,
        casos_atencion=casos_atencion,
        reincidentes=reincidentes,
        filtros_activos=filtros_activos,
        fechas_disponibles=fechas_disponibles,
        anios_disponibles=anios_disponibles,
    )


@dashboard.route("/dashboard/hub")
@login_required
def dashboards_hub():
    """Portal de inicio del rol gerente (vista ejecutiva de solo lectura)."""
    if current_user.rol.lower() not in ("gerente", "admin"):
        abort(403)
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

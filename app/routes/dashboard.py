from datetime import date

from flask import (
    Blueprint,
    url_for,
    redirect,
    render_template,
    abort,
)

from flask_login import (
    login_required,
    current_user
)

from sqlalchemy import func
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

    # ── Reportes operacionales ──────────────────────────────────
    neo_total       = ReporteOperacional.query.count()
    neo_abiertos    = ReporteOperacional.query.filter_by(estado="Abierto").count()
    neo_respondidos = ReporteOperacional.query.filter_by(estado="Respondido").count()
    neo_cerrados    = ReporteOperacional.query.filter_by(estado="Cerrado").count()
    neo_conformes   = ReporteOperacional.query.filter_by(conformidad_neo="Conforme").count()
    neo_no_conf     = ReporteOperacional.query.filter_by(conformidad_neo="No conforme").count()
    neo_hoy         = ReporteOperacional.query.filter_by(fecha_reporte=hoy).count()

    # ── Horas extras ───────────────────────────────────────────
    he_total     = HoraExtra.query.count()
    he_pendiente = HoraExtra.query.filter_by(estado="PENDIENTE").count()
    he_conforme  = HoraExtra.query.filter_by(estado="CONFORME").count()
    he_no_conf   = HoraExtra.query.filter_by(estado="NO CONFORME").count()
    he_desc      = HoraExtra.query.filter_by(estado="DESCONTADA").count()
    he_hrs_rep   = db.session.query(func.sum(HoraExtra.horas_reportadas)).scalar() or 0
    he_hrs_auth  = db.session.query(func.sum(HoraExtra.horas_autorizadas)).filter(
        HoraExtra.estado.in_(["CONFORME", "DESCONTADA"])
    ).scalar() or 0

    # ── Compromisos ────────────────────────────────────────────
    comp_total    = Compromiso.query.count()
    comp_cerrados = Compromiso.query.filter_by(estado="Cerrado").count()
    comp_vencidos = Compromiso.query.filter(
        Compromiso.estado != "Cerrado",
        Compromiso.fecha_entrega < hoy
    ).count()
    comp_abiertos = comp_total - comp_cerrados

    # ── General ────────────────────────────────────────────────
    contratos_activos = Contrato.query.filter_by(activo=True).count()
    usuarios_activos  = User.query.filter_by(activo=True).count()

    stats = {
        "neo": {
            "total": neo_total, "abiertos": neo_abiertos,
            "respondidos": neo_respondidos, "cerrados": neo_cerrados,
            "conformes": neo_conformes, "no_conformes": neo_no_conf,
            "hoy": neo_hoy,
            "pct_conf": round(neo_conformes / neo_total * 100, 1) if neo_total else 0,
        },
        "he": {
            "total": he_total, "pendiente": he_pendiente,
            "conforme": he_conforme, "no_conforme": he_no_conf, "descontada": he_desc,
            "hrs_reportadas": round(he_hrs_rep, 1),
            "hrs_autorizadas": round(he_hrs_auth, 1),
        },
        "comp": {
            "total": comp_total, "cerrados": comp_cerrados,
            "abiertos": comp_abiertos, "vencidos": comp_vencidos,
            "pct_cierre": round(comp_cerrados / comp_total * 100, 1) if comp_total else 0,
        },
        "general": {
            "contratos": contratos_activos,
            "usuarios": usuarios_activos,
            "hoy": hoy.strftime("%d/%m/%Y"),
        },
    }

    return render_template("dashboard/indicadores.html", stats=stats)


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

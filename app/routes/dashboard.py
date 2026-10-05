from flask import (
    Blueprint,
    url_for,
    redirect,
    render_template,
)

from flask_login import (
    login_required,
    current_user
)


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

@dashboard.route("/dashboard/hub")
@login_required
def dashboards_hub():
    """Portal de inicio del rol gerente (vista ejecutiva de solo lectura)."""
    groups = [
        {
            "name": "Dashboards Ejecutivos", "icon": "bi-bar-chart-line-fill", "tint": "#0891B2",
            "items": [
                {"label": "Dashboard HE", "icon": "bi-clock-history", "url": url_for("he_bp.he_dashboard"),
                 "desc": "KPIs de horas extras, tipos de HE, límite legal y valor de nómina"},
                {"label": "Preoperacionales", "icon": "bi-truck", "url": url_for("coordinador.preoperacionales"),
                 "desc": "Estado de inspecciones preoperacionales por sede y contrato"},
            ],
        },
        {
            "name": "Compromisos", "icon": "bi-calendar-check", "tint": "#D97706",
            "items": [
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

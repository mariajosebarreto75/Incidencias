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
# HUB DE DASHBOARDS
# ======================

@dashboard.route("/dashboard/hub")
@login_required
def dashboards_hub():
    rol = current_user.rol.lower()
    home_por_rol = {
        "neo":         "neo.home_neo",
        "coordinador": "coordinador.dashboard_coordinador",
        "admin":       "admin_bp.dashboard",
        "director":    "dashboard.director",
        "gerente":     "dashboard.dashboards_hub",
    }
    return render_template(
        "dashboard/hub.html",
        home_endpoint=home_por_rol.get(rol),
    )


# =====================================
# DASHBOARD GERENCIAL (eliminado)
# =====================================

@dashboard.route("/dashboard-gerencial")
@login_required
def indicadores():
    return redirect(url_for("dashboard.dashboards_hub"))

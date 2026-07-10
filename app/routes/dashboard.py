from flask import (
    Blueprint,
    render_template
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

@dashboard.route(
    "/director"
)

@login_required
def director():

    return f"""

    Bienvenido Director:

    {current_user.nombre_completo}

    """
from flask import (

    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash

)

from flask_login import (

    login_user,
    logout_user,
    login_required

)

from app.models.user import User


auth = Blueprint(
    "auth",
    __name__
)


# ======================
# LOGIN
# ======================

@auth.route(
    "/login",
    methods=["GET", "POST"]
)

def login():

    if request.method == "POST":

        username = request.form.get(
            "username"
        )

        password = request.form.get(
            "password"
        )

        user = User.query.filter_by(
            username=username,
            activo=True
        ).first()

        if not user:

            flash(
                "Usuario no encontrado",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )

        # ======================
        # TEMPORAL
        # PASSWORD SIMPLE
        # ======================

        if user.password_hash != password:

            flash(
                "Contraseña incorrecta",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )

        login_user(user)

        # ======================
        # ROLES
        # ======================

        if user.rol.lower() == "admin":

            return redirect(
                url_for("admin_bp.dashboard")
            )

        elif user.rol.lower() == "coordinador":

            return redirect(
                url_for(
                    "coordinador.dashboard_coordinador"
                )
            )

        elif user.rol.lower() == "neo":

            return redirect(
                url_for(
                    "neo.home_neo"
                )
            )

        elif user.rol.lower() == "director":

            return redirect(
                url_for(
                    "dashboard.director"
                )
            )

        return redirect("/")

    return render_template(
        "login.html"
    )


# ======================
# LOGOUT
# ======================

@auth.route("/logout")

@login_required
def logout():

    logout_user()

    return redirect(
        url_for("auth.login")
    )
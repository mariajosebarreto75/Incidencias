from flask import (

    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify

)

from flask_login import (

    login_user,
    logout_user,
    login_required

)

from app.models.user import User
from app.extensions import db


auth = Blueprint(
    "auth",
    __name__
)

MAX_INTENTOS = 3


# ======================
# LOGIN
# ======================

@auth.route(
    "/login",
    methods=["GET", "POST"]
)

def login():

    show_cambio_pwd = False

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Resetear contador si cambiaron de usuario
        if session.get("login_usuario") != username:
            session["login_intentos"] = 0
            session["login_usuario"]  = username

        user = User.query.filter_by(
            username=username,
            activo=True
        ).first()

        if not user:
            flash("Usuario no encontrado", "danger")
            return redirect(url_for("auth.login"))

        if user.password_hash != password:
            session["login_intentos"] = session.get("login_intentos", 0) + 1
            intentos = session["login_intentos"]

            if intentos >= MAX_INTENTOS:
                show_cambio_pwd = True
                return render_template(
                    "login.html",
                    show_cambio_pwd=True,
                    username_bloqueado=username
                )

            restantes = MAX_INTENTOS - intentos
            flash(
                f"Contraseña incorrecta. {'1 intento restante' if restantes == 1 else f'{restantes} intentos restantes'}",
                "danger"
            )
            return redirect(url_for("auth.login"))

        # Login exitoso — limpiar intentos
        session.pop("login_intentos", None)
        session.pop("login_usuario",  None)
        login_user(user)

        if user.rol.lower() == "admin":
            return redirect(url_for("admin_bp.dashboard"))
        elif user.rol.lower() == "coordinador":
            return redirect(url_for("coordinador.dashboard_coordinador"))
        elif user.rol.lower() == "neo":
            return redirect(url_for("neo.home_neo"))
        elif user.rol.lower() == "director":
            return redirect(url_for("dashboard.director"))

        return redirect("/")

    return render_template("login.html", show_cambio_pwd=False)


# ======================
# CAMBIAR CONTRASEÑA
# (sin autenticación — desde login)
# ======================

@auth.route("/cambiar-password", methods=["POST"])
def cambiar_password():
    username      = (request.form.get("username") or "").strip()
    nueva         = (request.form.get("nueva_password") or "").strip()
    confirmar     = (request.form.get("confirmar_password") or "").strip()

    if not username or not nueva:
        flash("Completa todos los campos.", "danger")
        return redirect(url_for("auth.login"))

    if nueva != confirmar:
        flash("Las contraseñas no coinciden.", "danger")
        return render_template("login.html", show_cambio_pwd=True, username_bloqueado=username)

    if len(nueva) < 4:
        flash("La contraseña debe tener al menos 4 caracteres.", "danger")
        return render_template("login.html", show_cambio_pwd=True, username_bloqueado=username)

    user = User.query.filter_by(username=username, activo=True).first()
    if not user:
        flash("Usuario no encontrado.", "danger")
        return redirect(url_for("auth.login"))

    user.password_hash = nueva
    db.session.commit()

    # Limpiar intentos fallidos
    session.pop("login_intentos", None)
    session.pop("login_usuario",  None)

    flash("Contraseña actualizada correctamente. Ya puedes iniciar sesión.", "success")
    return redirect(url_for("auth.login"))


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
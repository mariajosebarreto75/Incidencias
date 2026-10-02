import re

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, session
)
from flask_login import login_user, logout_user, login_required

from app.models.user import User
from app.extensions import db


auth = Blueprint("auth", __name__)

MAX_INTENTOS = 3
_SESSION_MCP  = "mcp_uid"   # user_id pendiente de cambio obligatorio


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validar_nueva_pwd(pwd: str, pwd_actual_hash: str = None) -> str | None:
    """Devuelve mensaje de error o None si es válida."""
    from werkzeug.security import check_password_hash
    if len(pwd) < 8:
        return "La contraseña debe tener mínimo 8 caracteres."
    if not re.search(r"[A-Z]", pwd):
        return "Debe incluir al menos una letra mayúscula."
    if not re.search(r"[a-z]", pwd):
        return "Debe incluir al menos una letra minúscula."
    if not re.search(r"\d", pwd):
        return "Debe incluir al menos un número."
    if not re.search(r"[^A-Za-z0-9]", pwd):
        return "Debe incluir al menos un carácter especial."
    if pwd_actual_hash and check_password_hash(pwd_actual_hash, pwd):
        return "La nueva contraseña no puede ser igual a la anterior."
    return None


def _redirect_por_rol(user: User):
    rol = user.rol.lower()
    if rol == "admin":
        return redirect(url_for("admin_bp.dashboard"))
    if rol == "coordinador":
        return redirect(url_for("coordinador.dashboard_coordinador"))
    if rol == "neo":
        return redirect(url_for("neo.home_neo"))
    if rol == "director":
        return redirect(url_for("coordinador.dashboard_coordinador"))
    if rol == "supervisor":
        return redirect(url_for("coordinador.dashboard_supervisor"))
    if rol == "gerente":
        return redirect(url_for("dashboard.dashboards_hub"))
    return redirect("/")


# ── LOGIN ─────────────────────────────────────────────────────────────────────

@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if session.get("login_usuario") != username:
            session["login_intentos"] = 0
            session["login_usuario"]  = username

        user = User.query.filter_by(username=username, activo=True).first()
        if not user:
            flash("Usuario no encontrado.", "danger")
            return redirect(url_for("auth.login"))

        pwd_ok = user.check_password(password)

        if not pwd_ok:
            session["login_intentos"] = session.get("login_intentos", 0) + 1
            intentos = session["login_intentos"]
            if intentos >= MAX_INTENTOS:
                return render_template("login.html", show_cambio_pwd=True,
                                       username_bloqueado=username)
            restantes = MAX_INTENTOS - intentos
            flash(
                f"Contraseña incorrecta. "
                f"{'1 intento restante' if restantes == 1 else f'{restantes} intentos restantes'}",
                "danger"
            )
            return redirect(url_for("auth.login"))

        session.pop("login_intentos", None)
        session.pop("login_usuario",  None)

        # ── Cambio obligatorio o contraseña expirada (no aplica a admin) ──────
        if user.rol.lower() != "admin":
            if user.must_change_password or user.password_expirada():
                user.must_change_password = True
                from app.extensions import db as _db
                _db.session.commit()
                session[_SESSION_MCP] = user.id
                return redirect(url_for("auth.cambio_obligatorio"))

        login_user(user)
        return _redirect_por_rol(user)

    return render_template("login.html", show_cambio_pwd=False)


# ── CAMBIO OBLIGATORIO ────────────────────────────────────────────────────────

@auth.route("/cambio-obligatorio", methods=["GET"])
def cambio_obligatorio():
    uid = session.get(_SESSION_MCP)
    if not uid:
        return redirect(url_for("auth.login"))
    user = db.session.get(User, uid)
    if not user or not user.must_change_password:
        session.pop(_SESSION_MCP, None)
        return redirect(url_for("auth.login"))
    return render_template("auth/cambio_obligatorio.html",
                           etapa="formulario", username=user.username)


@auth.route("/cambio-obligatorio/guardar", methods=["POST"])
def cambio_obligatorio_guardar():
    """Valida y aplica el cambio de contraseña directamente."""
    uid = session.get(_SESSION_MCP)
    if not uid:
        return redirect(url_for("auth.login"))
    user = db.session.get(User, uid)
    if not user or not user.must_change_password:
        return redirect(url_for("auth.login"))

    pwd_actual   = request.form.get("pwd_actual", "")
    nueva        = request.form.get("nueva", "").strip()
    confirmacion = request.form.get("confirmacion", "").strip()

    if not user.check_password(pwd_actual):
        flash("La contraseña actual es incorrecta.", "danger")
        return render_template("auth/cambio_obligatorio.html", username=user.username)

    error = _validar_nueva_pwd(nueva, user.password_hash)
    if error:
        flash(error, "danger")
        return render_template("auth/cambio_obligatorio.html", username=user.username)

    if nueva != confirmacion:
        flash("Las contraseñas no coinciden.", "danger")
        return render_template("auth/cambio_obligatorio.html", username=user.username)

    user.set_password(nueva)
    user.must_change_password = False
    db.session.commit()

    session.pop(_SESSION_MCP, None)

    login_user(user)
    flash("Contraseña actualizada correctamente. ¡Bienvenido!", "success")
    return _redirect_por_rol(user)


# ── CAMBIAR CONTRASEÑA (pantalla de bloqueo por intentos fallidos) ────────────

@auth.route("/cambiar-password", methods=["POST"])
def cambiar_password():
    username  = (request.form.get("username") or "").strip()
    nueva     = (request.form.get("nueva_password") or "").strip()
    confirmar = (request.form.get("confirmar_password") or "").strip()

    if session.get("login_usuario") != username or session.get("login_intentos", 0) < MAX_INTENTOS:
        flash("No se puede cambiar la contraseña en este momento.", "danger")
        return redirect(url_for("auth.login"))

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

    user.set_password(nueva)
    db.session.commit()

    session.pop("login_intentos", None)
    session.pop("login_usuario",  None)
    flash("Contraseña actualizada correctamente. Ya puedes iniciar sesión.", "success")
    return redirect(url_for("auth.login"))


# ── LOGOUT ─────────────────────────────────────────────────────────────────────

@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))



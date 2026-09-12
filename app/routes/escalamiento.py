"""
Rutas del sistema de escalamiento de incidencias.
- NEO responde si la incidencia sigue activa
- Supervisor/Coordinador/Director gestionan (cierran) el escalamiento
- Vista de escalamientos activos
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.escalamiento import EscalamientoIncidencia
from app.services.escalamiento_service import (
    registrar_respuesta_neo,
    gestionar_escalamiento,
)

esc_bp = Blueprint("esc_bp", __name__)


# ── NEO responde al check ─────────────────────────────────────────────────────

@esc_bp.route("/neo/escalamiento/<int:esc_id>/responder", methods=["GET", "POST"])
@login_required
def responder_neo(esc_id):
    esc = EscalamientoIncidencia.query.get_or_404(esc_id)
    reporte = esc.reporte

    if request.method == "POST":
        sigue = request.form.get("sigue") == "si"
        resultado = registrar_respuesta_neo(esc_id, sigue, current_user.username)
        if resultado["ok"]:
            flash(resultado["mensaje"], "success")
        else:
            flash(resultado["mensaje"], "danger")
        return redirect(url_for("neo.home_neo"))

    return render_template(
        "escalamiento/responder_neo.html",
        esc=esc,
        reporte=reporte,
    )


# ── Supervisor / Coordinador / Director gestiona ──────────────────────────────

@esc_bp.route("/escalamiento/<int:esc_id>/gestionar", methods=["POST"])
@login_required
def gestionar(esc_id):
    notas = request.form.get("notas", "")
    resultado = gestionar_escalamiento(esc_id, current_user, notas)
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(resultado)
    if resultado["ok"]:
        flash(resultado["mensaje"], "success")
    else:
        flash(resultado["mensaje"], "danger")
    return redirect(request.referrer or url_for("neo.home_neo"))


# ── API: badge de escalamientos activos para el usuario ──────────────────────

@esc_bp.route("/escalamiento/badge")
@login_required
def badge():
    """Cuenta escalamientos activos relevantes para el usuario actual."""
    rol = current_user.rol.lower()
    estados_activos = [
        "supervisor_notificado", "coordinador_notificado",
        "director_notificado", "gerencia_notificada",
        "esperando_neo_1", "esperando_neo_2", "cerrado_sin_gestion",
    ]
    count = EscalamientoIncidencia.query.filter(
        EscalamientoIncidencia.estado.in_(estados_activos)
    ).count()
    return jsonify({"activos": count})


# ── Lista de escalamientos (admin/director/coordinador) ───────────────────────

@esc_bp.route("/escalamientos")
@login_required
def lista():
    rol = current_user.rol.lower()
    if rol not in ("admin", "director", "coordinador", "supervisor"):
        flash("Sin acceso", "danger")
        return redirect(url_for("neo.home_neo"))

    estados_filter = request.args.get("estado", "")
    q = EscalamientoIncidencia.query.order_by(EscalamientoIncidencia.creado_at.desc())
    if estados_filter:
        q = q.filter_by(estado=estados_filter)

    escalamientos = q.limit(100).all()
    return render_template(
        "escalamiento/lista.html",
        escalamientos=escalamientos,
        estado_filtro=estados_filter,
    )

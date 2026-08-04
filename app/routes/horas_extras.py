from datetime import datetime, date
from functools import wraps
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.hora_extra import HoraExtra, CONCEPTOS_HE, FACTOR_HE
from app.models.contrato import Contrato
from app.models.persona import Persona
from app.models.user_contrato import UserContrato

he_bp = Blueprint("he_bp", __name__)

MODULOS = {
    "horas_extras": "Horas Extras",
}


def permiso_requerido(permiso):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.tiene_permiso(permiso):
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def _contratos_del_usuario():
    if current_user.rol.lower() in ("admin", "neo"):
        return Contrato.query.filter_by(activo=True).order_by(Contrato.contrato).all()
    nombres = [uc.contrato for uc in UserContrato.query.filter_by(user_id=current_user.id).all()]
    return Contrato.query.filter(Contrato.contrato.in_(nombres), Contrato.activo == True).order_by(Contrato.contrato).all()


def _ids_contratos_usuario():
    """Devuelve set de contrato_id permitidos para el usuario actual (coordinadores)."""
    nombres = [uc.contrato for uc in UserContrato.query.filter_by(user_id=current_user.id).all()]
    return {c.id for c in Contrato.query.filter(Contrato.contrato.in_(nombres)).all()}


# ── API: buscar persona por cédula ────────────────────────────────────────────
@he_bp.route("/api/he/persona")
@login_required
def api_persona_he():
    cedula = request.args.get("cedula", "").strip()
    if not cedula:
        return jsonify({"ok": False})
    p = Persona.query.filter_by(Documento=cedula).first()
    if not p:
        return jsonify({"ok": False})
    return jsonify({"ok": True, "nombre": p.Nombre, "salario": p.Salario})


# ── API: listar registros (coordinador: solo los suyos; NEO: todos) ────────────
@he_bp.route("/api/he/registros")
@login_required
def api_he_registros():
    q = HoraExtra.query
    if current_user.rol.lower() == "coordinador":
        ids = _ids_contratos_usuario()
        q = q.filter(HoraExtra.contrato_id.in_(ids))

    contrato_id = request.args.get("contrato_id", type=int)
    mes = request.args.get("mes", "")
    estado = request.args.get("estado", "")

    if contrato_id:
        q = q.filter(HoraExtra.contrato_id == contrato_id)
    if mes:
        try:
            year, month = mes.split("-")
            q = q.filter(
                db.extract("year",  HoraExtra.fecha_labor) == int(year),
                db.extract("month", HoraExtra.fecha_labor) == int(month),
            )
        except Exception:
            pass
    if estado:
        q = q.filter(HoraExtra.estado == estado)

    registros = q.order_by(HoraExtra.fecha_reporte.desc()).all()
    return jsonify([r.to_dict() for r in registros])


# ── COORDINADOR: página de registro ──────────────────────────────────────────
@he_bp.route("/coordinador/horas-extras")
@login_required
def he_coordinador():
    contratos = _contratos_del_usuario()
    return render_template(
        "coordinador/horas_extras.html",
        contratos=contratos,
        conceptos=CONCEPTOS_HE,
        title="Horas Extras",
    )


# ── API: guardar uno o varios registros (POST) ────────────────────────────────
@he_bp.route("/api/he/guardar", methods=["POST"])
@login_required
def api_he_guardar():
    data = request.get_json(silent=True) or {}
    filas = data.get("filas", [])
    if not filas:
        return jsonify({"ok": False, "msg": "Sin filas"}), 400

    ids_permitidos = _ids_contratos_usuario() if current_user.rol.lower() == "coordinador" else None

    guardados = []
    for f in filas:
        contrato_id = f.get("contrato_id")
        if not contrato_id:
            continue
        if ids_permitidos is not None and int(contrato_id) not in ids_permitidos:
            return jsonify({"ok": False, "msg": "Contrato no asignado a su usuario"}), 403
        concepto = f.get("id_concepto", "")
        he = HoraExtra(
            contrato_id        = contrato_id,
            fecha_labor        = date.fromisoformat(f["fecha_labor"]) if f.get("fecha_labor") else date.today(),
            cedula             = f.get("cedula", "").strip(),
            nombre             = f.get("nombre", "").strip(),
            recurso            = f.get("recurso", "").strip(),
            id_concepto        = concepto,
            tipo_he            = CONCEPTOS_HE.get(concepto, ""),
            horas_reportadas   = float(f.get("horas_reportadas") or 0),
            horas_compensadas  = float(f.get("horas_compensadas") or 0),
            autorizacion_coord = f.get("autorizacion_coord", ""),
            justificacion      = f.get("justificacion", "").strip(),
            observacion        = f.get("observacion", "").strip(),
            estado             = "PENDIENTE",
            reportado_por_id   = current_user.id,
            fecha_reporte      = datetime.utcnow(),
        )
        db.session.add(he)
        guardados.append(he)

    db.session.commit()
    return jsonify({"ok": True, "guardados": len(guardados)})


# ── API: actualizar registro (coordinador puede editar PENDIENTE) ─────────────
@he_bp.route("/api/he/<int:id>", methods=["PUT"])
@login_required
def api_he_actualizar(id):
    he = HoraExtra.query.get_or_404(id)
    if current_user.rol.lower() == "coordinador":
        if he.estado != "PENDIENTE":
            return jsonify({"ok": False, "msg": "Solo se pueden editar registros pendientes"}), 403
        if he.contrato_id not in _ids_contratos_usuario():
            return jsonify({"ok": False, "msg": "No autorizado"}), 403
    f = request.get_json(silent=True) or {}
    concepto = f.get("id_concepto", he.id_concepto)
    he.fecha_labor        = date.fromisoformat(f["fecha_labor"]) if f.get("fecha_labor") else he.fecha_labor
    he.cedula             = f.get("cedula", he.cedula)
    he.nombre             = f.get("nombre", he.nombre)
    he.recurso            = f.get("recurso", he.recurso)
    he.id_concepto        = concepto
    he.tipo_he            = CONCEPTOS_HE.get(concepto, he.tipo_he)
    he.horas_reportadas   = float(f.get("horas_reportadas") or he.horas_reportadas)
    he.horas_compensadas  = float(f.get("horas_compensadas") or 0)
    he.autorizacion_coord = f.get("autorizacion_coord", he.autorizacion_coord)
    he.justificacion      = f.get("justificacion", he.justificacion)
    he.observacion        = f.get("observacion", he.observacion)
    db.session.commit()
    return jsonify({"ok": True})


# ── API: eliminar registro (coordinador solo PENDIENTE) ───────────────────────
@he_bp.route("/api/he/<int:id>", methods=["DELETE"])
@login_required
def api_he_eliminar(id):
    he = HoraExtra.query.get_or_404(id)
    if current_user.rol.lower() == "coordinador":
        if he.estado != "PENDIENTE":
            return jsonify({"ok": False, "msg": "Solo se pueden eliminar registros pendientes"}), 403
        if he.contrato_id not in _ids_contratos_usuario():
            return jsonify({"ok": False, "msg": "No autorizado"}), 403
    db.session.delete(he)
    db.session.commit()
    return jsonify({"ok": True})


# ── NEO: página de validación ─────────────────────────────────────────────────
@he_bp.route("/neo/horas-extras")
@login_required
@permiso_requerido("horas_extras")
def he_neo():
    contratos = Contrato.query.filter_by(activo=True).order_by(Contrato.contrato).all()
    return render_template(
        "neo/horas_extras_validar.html",
        contratos=contratos,
        conceptos=CONCEPTOS_HE,
        title="Validar Horas Extras",
    )


# ── API: validar registro (NEO/admin) ─────────────────────────────────────────
@he_bp.route("/api/he/<int:id>/validar", methods=["POST"])
@login_required
@permiso_requerido("horas_extras")
def api_he_validar(id):
    he = HoraExtra.query.get_or_404(id)
    d = request.get_json(silent=True) or {}

    autorizacion = d.get("autorizacion_neo", "").upper()
    horas_auth   = d.get("horas_autorizadas")
    obs          = d.get("obs_neo", "").strip()

    if autorizacion not in ("APROBADA", "PARCIAL", "RECHAZADA"):
        return jsonify({"ok": False, "msg": "Autorización inválida"}), 400

    he.autorizacion_neo  = autorizacion
    he.horas_autorizadas = float(horas_auth) if horas_auth is not None else float(he.horas_reportadas)
    he.obs_neo           = obs
    he.estado            = autorizacion
    he.validado_por_id   = current_user.id
    he.fecha_validacion  = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True, "estado": he.estado})


# ── API: KPIs para NEO ────────────────────────────────────────────────────────
@he_bp.route("/api/he/kpis")
@login_required
def api_he_kpis():
    q = HoraExtra.query
    contrato_id = request.args.get("contrato_id", type=int)
    mes = request.args.get("mes", "")
    if contrato_id:
        q = q.filter(HoraExtra.contrato_id == contrato_id)
    if mes:
        try:
            year, month = mes.split("-")
            q = q.filter(
                db.extract("year",  HoraExtra.fecha_labor) == int(year),
                db.extract("month", HoraExtra.fecha_labor) == int(month),
            )
        except Exception:
            pass
    total      = q.count()
    pendientes = q.filter(HoraExtra.estado == "PENDIENTE").count()
    aprobadas  = q.filter(HoraExtra.estado == "APROBADA").count()
    parciales  = q.filter(HoraExtra.estado == "PARCIAL").count()
    rechazadas = q.filter(HoraExtra.estado == "RECHAZADA").count()
    hrs_rep    = db.session.query(db.func.sum(HoraExtra.horas_reportadas)).filter(
        HoraExtra.contrato_id == contrato_id if contrato_id else True
    ).scalar() or 0
    hrs_auth   = db.session.query(db.func.sum(HoraExtra.horas_autorizadas)).filter(
        HoraExtra.contrato_id == contrato_id if contrato_id else True
    ).scalar() or 0
    return jsonify({
        "total": total, "pendientes": pendientes, "aprobadas": aprobadas,
        "parciales": parciales, "rechazadas": rechazadas,
        "hrs_reportadas": float(hrs_rep), "hrs_autorizadas": float(hrs_auth),
    })

from datetime import datetime, date
from functools import wraps
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.hora_extra import HoraExtra, CONCEPTOS_HE, FACTOR_HE
from app.models.contrato import Contrato
from app.models.persona import Persona
from app.models.user_contrato import UserContrato
from app.models.supervisor import Supervisor

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


# ── API: supervisores por contrato ───────────────────────────────────────────
@he_bp.route("/api/he/supervisores")
@login_required
def api_he_supervisores():
    from app.models.supervisor import supervisor_contrato
    contrato_id = request.args.get("contrato_id", type=int)
    todos = Supervisor.query.filter_by(activo=True).order_by(Supervisor.nombre).all()
    if not contrato_id:
        return jsonify([s.nombre for s in todos])
    # IDs con al menos un contrato asignado
    con_contrato_ids = {
        row[0] for row in db.session.query(supervisor_contrato.c.supervisor_id).all()
    }
    # IDs asignados específicamente a este contrato
    asignados_ids = {
        row[0] for row in db.session.query(supervisor_contrato.c.supervisor_id)
        .filter(supervisor_contrato.c.contrato_id == contrato_id).all()
    }
    resultado = [
        s.nombre for s in todos
        if s.id in asignados_ids or s.id not in con_contrato_ids
    ]
    return jsonify(resultado)


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
            contrato_id       = contrato_id,
            fecha_labor       = date.fromisoformat(f["fecha_labor"]) if f.get("fecha_labor") else date.today(),
            cedula            = f.get("cedula", "").strip(),
            nombre            = f.get("nombre", "").strip(),
            recurso           = f.get("recurso", "").strip(),
            id_concepto       = concepto,
            tipo_he           = CONCEPTOS_HE.get(concepto, ""),
            horas_reportadas  = int(float(f.get("horas_reportadas") or 0)),
            horas_compensadas = int(float(f.get("horas_compensadas") or 0)),
            placa             = f.get("placa", "").strip(),
            hora_inicio       = f.get("hora_inicio", "").strip(),
            hora_fin          = f.get("hora_fin", "").strip(),
            supervisor        = f.get("supervisor", "").strip(),
            justificacion     = f.get("justificacion", "").strip(),
            observacion       = f.get("observacion", "").strip(),
            estado            = "PENDIENTE",
            reportado_por_id  = current_user.id,
            fecha_reporte     = datetime.utcnow(),
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
    he.horas_reportadas   = int(float(f.get("horas_reportadas") or he.horas_reportadas))
    he.horas_compensadas  = int(float(f.get("horas_compensadas") or 0))
    he.supervisor         = f.get("supervisor", he.supervisor)
    he.justificacion      = f.get("justificacion", he.justificacion)
    he.observacion        = f.get("observacion", he.observacion)
    if f.get("valor_hora")         is not None: he.valor_hora         = f["valor_hora"]
    if f.get("valor_extra_nomina") is not None: he.valor_extra_nomina = f["valor_extra_nomina"]
    if f.get("valor_extra")        is not None: he.valor_extra        = f["valor_extra"]
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

    if autorizacion not in ("CONFORME", "NO CONFORME", "DESCONTADA"):
        return jsonify({"ok": False, "msg": "Autorización inválida"}), 400

    he.autorizacion_neo  = autorizacion
    he.horas_autorizadas = int(float(horas_auth)) if horas_auth is not None else he.horas_reportadas
    he.obs_neo           = obs
    he.estado            = autorizacion
    he.validado_por_id   = current_user.id
    he.fecha_validacion  = datetime.utcnow()
    db.session.commit()
    return jsonify({
        "ok": True,
        "estado": he.estado,
        "validado_por":    current_user.nombre_completo,
        "fecha_validacion": he.fecha_validacion.strftime("%Y-%m-%d %H:%M"),
    })


# ── API: KPIs ────────────────────────────────────────────────────────────────
@he_bp.route("/api/he/kpis")
@login_required
def api_he_kpis():
    q = HoraExtra.query

    # Coordinadores solo ven sus contratos
    if current_user.rol.lower() == "coordinador":
        q = q.filter(HoraExtra.contrato_id.in_(_ids_contratos_usuario()))

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

    def _hrs_rep(q_base):
        return float(q_base.with_entities(
            db.func.coalesce(db.func.sum(HoraExtra.horas_reportadas), 0)
        ).scalar() or 0)

    def _hrs_auth(q_base):
        return float(q_base.with_entities(
            db.func.coalesce(db.func.sum(HoraExtra.horas_autorizadas), 0)
        ).scalar() or 0)

    q_conf   = q.filter(HoraExtra.estado == "CONFORME")
    q_noconf = q.filter(HoraExtra.estado == "NO CONFORME")
    q_desc   = q.filter(HoraExtra.estado == "DESCONTADA")
    q_pend   = q.filter(HoraExtra.estado == "PENDIENTE")

    return jsonify({
        "total":            q.count(),
        "pendientes":       q_pend.count(),
        "conformes":        q_conf.count(),
        "no_conformes":     q_noconf.count(),
        "descontadas":      q_desc.count(),
        "hrs_reportadas":   _hrs_rep(q),
        "hrs_conformes":    _hrs_rep(q_conf),
        "hrs_no_conformes": _hrs_rep(q_noconf),
        "hrs_descontadas":  _hrs_rep(q_desc),
        "hrs_pendientes":   _hrs_rep(q_pend),
        "hrs_autorizadas":  _hrs_auth(q),
    })

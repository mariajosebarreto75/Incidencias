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
from app.models.he_corte import HeCorte

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
    mes         = request.args.get("mes", "")
    estado      = request.args.get("estado", "")
    corte_id    = request.args.get("corte_id", type=int)

    if corte_id:
        q = q.filter(HoraExtra.corte_id == corte_id)
    elif contrato_id:
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


# ── HUB: página de selección de módulo ───────────────────────────────────────
@he_bp.route("/horas-extras")
@login_required
def he_hub():
    rol = current_user.rol.lower()
    puede_ingresar = rol in ("coordinador", "admin")
    puede_validar  = rol in ("neo", "admin") or current_user.tiene_permiso("horas_extras")
    if rol == "coordinador":
        base_template = "coordinador/navbarcoor.html"
    elif rol == "neo":
        base_template = "neo/navbNeo.html"
    else:
        base_template = "neo/navbNeo.html"
    return render_template(
        "horas_extras/hub.html",
        base_template=base_template,
        puede_ingresar=puede_ingresar,
        puede_validar=puede_validar,
        title="Horas Extras",
    )


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
    # Cache de contratos por nombre para no repetir queries
    _contrato_cache = {}
    # Cache de cortes: (contrato_id, fecha) -> corte_id
    _corte_cache = {}

    for f in filas:
        contrato_id = f.get("contrato_id")

        # Si no viene contrato_id, intentar resolver por nombre (insensible a mayúsculas/espacios)
        if not contrato_id and f.get("contrato"):
            nombre_c = str(f["contrato"]).strip()
            if nombre_c not in _contrato_cache:
                c = Contrato.query.filter(
                    db.func.lower(db.func.trim(Contrato.contrato)) == nombre_c.lower()
                ).first()
                _contrato_cache[nombre_c] = c.id if c else None
            contrato_id = _contrato_cache[nombre_c]

        if not contrato_id:
            continue
        contrato_id = int(contrato_id)
        if ids_permitidos is not None and contrato_id not in ids_permitidos:
            return jsonify({"ok": False, "msg": "Contrato no asignado a su usuario"}), 403

        concepto   = str(f.get("id_concepto") or "").strip()
        # tipo_he: usar el del archivo si viene, si no calcular del concepto
        tipo_he    = str(f.get("tipo_he") or CONCEPTOS_HE.get(concepto, "")).strip()
        # autorizacion_neo puede venir pre-cargada del archivo
        auth_neo   = str(f.get("autorizacion_neo") or "").strip().upper()
        hrs_auth   = f.get("horas_autorizadas")
        # estado basado en autorizacion_neo si viene
        if auth_neo in ("CONFORME", "NO CONFORME", "DESCONTADA"):
            estado = auth_neo
        else:
            estado = "PENDIENTE"
            auth_neo = ""

        he = HoraExtra(
            contrato_id       = contrato_id,
            fecha_labor       = date.fromisoformat(f["fecha_labor"]) if f.get("fecha_labor") else date.today(),
            cedula            = str(f.get("cedula") or "").strip(),
            nombre            = str(f.get("nombre") or "").strip(),
            recurso           = str(f.get("recurso") or "").strip(),
            id_concepto       = concepto,
            tipo_he           = tipo_he,
            horas_reportadas  = int(float(f.get("horas_reportadas") or 0)),
            horas_compensadas = int(float(f.get("horas_compensadas") or 0)),
            placa             = str(f.get("placa") or "").strip(),
            hora_inicio       = str(f.get("hora_inicio") or "").strip(),
            hora_fin          = str(f.get("hora_fin") or "").strip(),
            autorizacion_sup  = str(f.get("autorizacion_sup") or "").strip(),
            justificacion     = str(f.get("justificacion") or "").strip(),
            observacion       = str(f.get("observacion") or "").strip(),
            valor_extra_nomina= float(f["valor_extra_nomina"]) if f.get("valor_extra_nomina") not in (None,"","0") else None,
            valor_extra       = float(f["valor_extra"]) if f.get("valor_extra") not in (None,"","0") else None,
            autorizacion_neo  = auth_neo or None,
            horas_autorizadas = int(float(hrs_auth)) if hrs_auth not in (None,"") else None,
            estado            = estado,
            reportado_por_id  = current_user.id,
            fecha_reporte     = datetime.utcnow(),
        )
        # Asignar al corte cuyo período cubre la fecha_labor
        if he.fecha_labor:
            cache_key = (contrato_id, he.fecha_labor)
            if cache_key not in _corte_cache:
                corte = HeCorte.query.filter(
                    HeCorte.fecha_inicio <= he.fecha_labor,
                    HeCorte.fecha_fin   >= he.fecha_labor,
                    db.or_(HeCorte.contrato_id == contrato_id, HeCorte.contrato_id == None)
                ).order_by(HeCorte.contrato_id.desc().nullslast()).first()
                _corte_cache[cache_key] = corte.id if corte else None
            he.corte_id = _corte_cache[cache_key]

        db.session.add(he)
        guardados.append(he)

    db.session.commit()
    return jsonify({"ok": True, "guardados": len(guardados)})


# ── API: obtener un registro por id ──────────────────────────────────────────
@he_bp.route("/api/he/<int:id>", methods=["GET"])
@login_required
def api_he_get(id):
    he = HoraExtra.query.get_or_404(id)
    if current_user.rol.lower() == "coordinador":
        if he.contrato_id not in _ids_contratos_usuario():
            return jsonify({"ok": False, "msg": "No autorizado"}), 403
    return jsonify({"ok": True, "registro": he.to_dict()})


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
    he.autorizacion_sup   = f.get("autorizacion_sup", he.autorizacion_sup)
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


# ══════════════════════════════════════════════════════════════════════════════
# CORTES
# ══════════════════════════════════════════════════════════════════════════════

@he_bp.route("/api/he/cortes")
@login_required
def api_he_cortes_list():
    """Lista de cortes, opcionalmente filtrado por contrato."""
    contrato_id = request.args.get("contrato_id", type=int)
    q = HeCorte.query
    if contrato_id:
        q = q.filter((HeCorte.contrato_id == contrato_id) | (HeCorte.contrato_id == None))
    elif current_user.rol.lower() == "coordinador":
        ids = _ids_contratos_usuario()
        q = q.filter((HeCorte.contrato_id.in_(ids)) | (HeCorte.contrato_id == None))
    cortes = q.order_by(HeCorte.fecha_inicio.desc()).all()
    return jsonify([c.to_dict() for c in cortes])


@he_bp.route("/api/he/cortes", methods=["POST"])
@login_required
def api_he_cortes_crear():
    """Crear un nuevo corte (y opcionalmente asignar registros sueltos a él)."""
    d = request.get_json(silent=True) or {}
    fi = d.get("fecha_inicio")
    ff = d.get("fecha_fin")
    nombre = d.get("nombre", "").strip()
    if not fi or not ff:
        return jsonify({"ok": False, "msg": "fecha_inicio y fecha_fin son requeridos"}), 400

    fecha_inicio = date.fromisoformat(fi)
    fecha_fin    = date.fromisoformat(ff)
    if not nombre:
        meses = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
        nombre = f"{fecha_inicio.day} {meses[fecha_inicio.month-1]} – {fecha_fin.day} {meses[fecha_fin.month-1]} {fecha_fin.year}"

    contrato_id = d.get("contrato_id") or None

    corte = HeCorte(
        nombre        = nombre,
        fecha_inicio  = fecha_inicio,
        fecha_fin     = fecha_fin,
        contrato_id   = contrato_id,
        estado        = "ABIERTO",
        creado_por_id = current_user.id,
    )
    db.session.add(corte)
    db.session.flush()  # obtener id

    # Asignar registros dentro del período a este corte
    q = HoraExtra.query.filter(
        HoraExtra.fecha_labor >= fecha_inicio,
        HoraExtra.fecha_labor <= fecha_fin,
        HoraExtra.corte_id == None,
    )
    if contrato_id:
        q = q.filter(HoraExtra.contrato_id == contrato_id)
    asignados = q.update({"corte_id": corte.id}, synchronize_session=False)

    db.session.commit()
    return jsonify({"ok": True, "corte": corte.to_dict(), "registros_asignados": asignados})


@he_bp.route("/api/he/cortes/<int:corte_id>/cerrar", methods=["POST"])
@login_required
def api_he_cortes_cerrar(corte_id):
    """Cerrar un corte activo."""
    corte = HeCorte.query.get_or_404(corte_id)
    if corte.estado == "CERRADO":
        return jsonify({"ok": False, "msg": "El corte ya está cerrado"}), 400
    d = request.get_json(silent=True) or {}
    corte.estado         = "CERRADO"
    corte.cerrado_por_id = current_user.id
    corte.fecha_cierre   = datetime.utcnow()
    corte.observacion    = d.get("observacion", corte.observacion)
    db.session.commit()
    return jsonify({"ok": True, "corte": corte.to_dict()})


@he_bp.route("/api/he/cortes/<int:corte_id>")
@login_required
def api_he_cortes_detalle(corte_id):
    """Registros de un corte específico."""
    corte = HeCorte.query.get_or_404(corte_id)
    registros = HoraExtra.query.filter_by(corte_id=corte_id).order_by(HoraExtra.fecha_labor).all()
    return jsonify({
        "corte":     corte.to_dict(),
        "registros": [r.to_dict() for r in registros],
    })

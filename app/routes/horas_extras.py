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
from app.models.he_config import HeConfig

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


# ── API: resolver nombres por cédulas (batch) ─────────────────────────────────
@he_bp.route("/api/he/personas/nombres", methods=["POST"])
@login_required
def api_personas_nombres():
    cedulas = request.json or []
    if not cedulas:
        return jsonify({})
    personas = Persona.query.filter(Persona.Documento.in_(cedulas)).all()
    return jsonify({p.Documento: p.Nombre for p in personas})


# ── API: listar registros (coordinador: solo los suyos; NEO: todos) ────────────
@he_bp.route("/api/he/registros")
@login_required
def api_he_registros():
    q = HoraExtra.query
    if current_user.rol.lower() == "coordinador":
        ids = _ids_contratos_usuario()
        q = q.filter(HoraExtra.contrato_id.in_(ids))

    contrato_id  = request.args.get("contrato_id", type=int)
    mes          = request.args.get("mes", "")
    estado       = request.args.get("estado", "")
    corte_id     = request.args.get("corte_id", type=int)
    fecha_desde  = request.args.get("fecha_desde", "")
    fecha_hasta  = request.args.get("fecha_hasta", "")
    id_concepto  = request.args.get("id_concepto", "")

    if contrato_id:
        q = q.filter(HoraExtra.contrato_id == contrato_id)

    if corte_id:
        corte_obj = HeCorte.query.get(corte_id)
        if corte_obj:
            from sqlalchemy import or_ as sa_or
            q = q.filter(sa_or(
                HoraExtra.corte_id == corte_id,
                db.and_(
                    HoraExtra.fecha_labor >= corte_obj.fecha_inicio,
                    HoraExtra.fecha_labor <= corte_obj.fecha_fin,
                )
            ))
        else:
            q = q.filter(HoraExtra.corte_id == corte_id)

    if fecha_desde and not corte_id:
        try:
            q = q.filter(HoraExtra.fecha_labor >= date.fromisoformat(fecha_desde))
        except Exception:
            pass
    if fecha_hasta and not corte_id:
        try:
            q = q.filter(HoraExtra.fecha_labor <= date.fromisoformat(fecha_hasta))
        except Exception:
            pass
    if mes and not fecha_desde and not fecha_hasta and not corte_id:
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
    if id_concepto:
        q = q.filter(HoraExtra.id_concepto == id_concepto)

    try:
        registros = q.order_by(HoraExtra.fecha_reporte.desc()).all()
        return jsonify([r.to_dict() for r in registros])
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


# ── DASHBOARD HE ─────────────────────────────────────────────────────────────
@he_bp.route("/he/dashboard")
@login_required
def he_dashboard():
    rol = current_user.rol.lower()
    if not (rol == "admin" or current_user.tiene_permiso("dashboard_he")):
        abort(403)
    contratos = _contratos_del_usuario() if rol == "admin" else _contratos_del_usuario()
    cortes    = HeCorte.query.order_by(HeCorte.fecha_inicio.desc()).all()
    if rol in ("coordinador",):
        base_template = "coordinador/navbarcoor.html"
    elif rol == "neo":
        base_template = "neo/navbNeo.html"
    else:
        base_template = "neo/navbNeo.html"
    return render_template("horas_extras/dashboard_he.html",
                           contratos=contratos, cortes=cortes,
                           base_template=base_template)


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
    contratos = _contratos_del_usuario() if puede_ingresar else []
    return render_template(
        "horas_extras/hub.html",
        base_template=base_template,
        puede_ingresar=puede_ingresar,
        puede_validar=puede_validar,
        contratos=contratos,
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

    # Pre-cargar contratos y cortes en memoria (evita N+1 queries)
    _contratos_lista = Contrato.query.all()
    todos_contratos  = {c.contrato.strip().lower(): c.id for c in _contratos_lista}
    contratos_nombre = {c.id: c.contrato for c in _contratos_lista}
    todos_cortes     = HeCorte.query.all()
    ahora            = datetime.utcnow()
    uid              = current_user.id

    def _cid(f):
        v = f.get("contrato_id")
        if v:
            return int(v)
        nombre = str(f.get("contrato") or "").strip().lower()
        # 1) Coincidencia exacta
        cid = todos_contratos.get(nombre)
        if cid:
            return cid
        # 2) Búsqueda parcial: el nombre del Excel está contenido en el nombre de la BD
        #    o viceversa (ej. "MTTO CHAPARRAL" ↔ "Tolima Mantenimiento (014) - MTTO - Chaparral")
        for bd_nombre, bd_id in todos_contratos.items():
            if nombre in bd_nombre or bd_nombre in nombre:
                return bd_id
        return None

    def _corte(cid, fl):
        if not fl:
            return None
        for c in todos_cortes:
            if c.fecha_inicio <= fl <= c.fecha_fin and c.contrato_id == cid:
                return c.id
        for c in todos_cortes:
            if c.fecha_inicio <= fl <= c.fecha_fin and c.contrato_id is None:
                return c.id
        return None

    def _num(v):
        try:
            return float(v) if v not in (None, "", "0", 0) else None
        except Exception:
            return None

    registros = []
    omitidos  = 0
    contratos_no_encontrados = {}   # nombre -> lista de filas
    for f in filas:
        cid = _cid(f)
        if not cid:
            nombre_contrato = str(f.get("contrato") or "").strip() or "(sin contrato)"
            if nombre_contrato not in contratos_no_encontrados:
                contratos_no_encontrados[nombre_contrato] = []
            contratos_no_encontrados[nombre_contrato].append(len(registros) + omitidos + 1)
            omitidos += 1
            continue
        if ids_permitidos is not None and cid not in ids_permitidos:
            return jsonify({"ok": False, "msg": "Contrato no asignado a su usuario"}), 403

        try:
            fl = date.fromisoformat(str(f["fecha_labor"])) if f.get("fecha_labor") else date.today()
        except Exception:
            fl = date.today()

        concepto = str(f.get("id_concepto") or "").strip().zfill(2) if str(f.get("id_concepto") or "").strip() else ""
        tipo_he  = str(f.get("tipo_he") or CONCEPTOS_HE.get(concepto, "")).strip()
        auth_neo = str(f.get("autorizacion_neo") or "").strip().upper()
        hrs_auth = f.get("horas_autorizadas")
        estado   = auth_neo if auth_neo in ("CONFORME", "NO CONFORME", "DESCONTADA") else "PENDIENTE"
        if estado == "PENDIENTE":
            auth_neo = None

        registros.append({
            "contrato_id":       cid,
            "fecha_labor":       fl,
            "cedula":            str(f.get("cedula")  or "").strip(),
            "nombre":            str(f.get("nombre")  or "").strip(),
            "recurso":           str(f.get("recurso") or "").strip(),
            "id_concepto":       concepto,
            "tipo_he":           tipo_he,
            "horas_reportadas":  int(float(f.get("horas_reportadas")  or 0)),
            "horas_compensadas": int(float(f.get("horas_compensadas") or 0)),
            "placa":             str(f.get("placa")       or "").strip(),
            "hora_inicio":       str(f.get("hora_inicio") or "").strip(),
            "hora_fin":          str(f.get("hora_fin")    or "").strip(),
            "autorizacion_sup":  str(f.get("autorizacion_sup") or "").strip(),
            "justificacion":     str(f.get("justificacion")    or "").strip(),
            "observacion":       str(f.get("observacion")      or "").strip(),
            "valor_extra_nomina":_num(f.get("valor_extra_nomina")),
            "valor_extra":       _num(f.get("valor_extra")),
            "autorizacion_neo":  auth_neo,
            "horas_autorizadas": int(float(hrs_auth)) if hrs_auth not in (None, "") else None,
            "estado":            estado,
            "reportado_por_id":  uid,
            "fecha_reporte":     ahora,
            "corte_id":          _corte(cid, fl),
        })

    if contratos_no_encontrados:
        detalle = [
            {"contrato": nombre, "filas": filas_cnt[:5], "total": len(filas_cnt)}
            for nombre, filas_cnt in contratos_no_encontrados.items()
        ]
        return jsonify({
            "ok": False,
            "contratos_no_encontrados": True,
            "msg": f"{omitidos} fila(s) tienen contratos que no existen en el sistema. Corrija los nombres antes de importar.",
            "detalle": detalle,
        }), 422

    if not registros:
        return jsonify({"ok": False, "msg": "Sin registros válidos"}), 400

    # ── Validación de duplicados ──────────────────────────────────────────────
    # Clave: contrato + cédula + concepto (normalizado 2 dígitos) + fecha + horas
    from sqlalchemy import tuple_ as sa_tuple
    claves_bd = sa_tuple(
        HoraExtra.contrato_id, HoraExtra.cedula,
        HoraExtra.id_concepto, HoraExtra.fecha_labor, HoraExtra.horas_reportadas
    )
    # Normalizar concepto para comparar: "3" → "03"
    def _norm_concepto(v):
        return str(v or "").strip().zfill(2)

    buscar = [(r["contrato_id"], r["cedula"], _norm_concepto(r["id_concepto"]),
               r["fecha_labor"], r["horas_reportadas"]) for r in registros]
    existentes = HoraExtra.query.filter(claves_bd.in_(
        [(r["contrato_id"], r["cedula"], r["id_concepto"],
          r["fecha_labor"], r["horas_reportadas"]) for r in registros]
    )).all()
    existentes_set = {
        (e.contrato_id, e.cedula, _norm_concepto(e.id_concepto),
         str(e.fecha_labor), e.horas_reportadas)
        for e in existentes
    }

    # 2) Separar válidos de duplicados (intra-lote + BD)
    lote_keys = {}
    registros_ok = []
    duplicados = []
    for i, r in enumerate(registros):
        k = (r["contrato_id"], r["cedula"], _norm_concepto(r["id_concepto"]),
             str(r["fecha_labor"]), r["horas_reportadas"])
        if k in lote_keys:
            duplicados.append({
                "fila": i + 1, "contrato": contratos_nombre.get(r["contrato_id"], ""),
                "cedula": r["cedula"], "concepto": r["id_concepto"],
                "fecha": str(r["fecha_labor"]), "hrs": r["horas_reportadas"],
                "motivo": f"Duplicado de fila {lote_keys[k] + 1} en este lote",
            })
        elif k in existentes_set:
            duplicados.append({
                "fila": i + 1, "contrato": contratos_nombre.get(r["contrato_id"], ""),
                "cedula": r["cedula"], "concepto": r["id_concepto"],
                "fecha": str(r["fecha_labor"]), "hrs": r["horas_reportadas"],
                "motivo": "Ya existe en la base de datos",
            })
        else:
            lote_keys[k] = i
            registros_ok.append(r)

    try:
        if registros_ok:
            db.session.bulk_insert_mappings(HoraExtra, registros_ok)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        import traceback
        return jsonify({"ok": False, "msg": str(e), "trace": traceback.format_exc()}), 500

    return jsonify({
        "ok": True,
        "guardados": len(registros_ok),
        "omitidos": omitidos,
        "duplicados_omitidos": len(duplicados),
        "detalle_duplicados": duplicados,
    })


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
    f = request.get_json(silent=True) or {}
    if current_user.rol.lower() == "coordinador":
        if he.contrato_id not in _ids_contratos_usuario():
            return jsonify({"ok": False, "msg": "No autorizado"}), 403
        if he.estado != "PENDIENTE":
            # No-PENDIENTE: solo horas_compensadas y observacion permitidos
            campos_permitidos = {"horas_compensadas", "observacion"}
            if any(k not in campos_permitidos for k in f if k != "placa"):
                # Si solo vienen campos permitidos, aplicar; sino bloquear
                claves = set(f.keys()) - campos_permitidos
                if claves:
                    return jsonify({"ok": False, "msg": "Solo se pueden editar registros pendientes"}), 403
            if "horas_compensadas" in f:
                he.horas_compensadas = int(float(f["horas_compensadas"] or 0))
            if "observacion" in f:
                he.observacion = f["observacion"]
            db.session.commit()
            return jsonify({"ok": True})
    concepto = str(f.get("id_concepto") or he.id_concepto or "").strip()
    concepto = concepto.zfill(2) if concepto else concepto
    he.fecha_labor        = date.fromisoformat(f["fecha_labor"]) if f.get("fecha_labor") else he.fecha_labor
    if "corte_id" in f:
        he.corte_id = int(f["corte_id"]) if f["corte_id"] else None
    he.cedula             = f.get("cedula", he.cedula)
    he.nombre             = f.get("nombre", he.nombre)
    he.recurso            = f.get("recurso", he.recurso)
    he.placa              = f.get("placa", he.placa)
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


# ── API: eliminar múltiples registros (solo NEO) ─────────────────────────────
@he_bp.route("/api/he/bulk-delete", methods=["POST"])
@login_required
def api_he_bulk_delete():
    if current_user.rol.lower() not in ("neo", "admin"):
        return jsonify({"ok": False, "msg": "No autorizado"}), 403
    ids = request.get_json(silent=True) or []
    if not ids:
        return jsonify({"ok": False, "msg": "Sin IDs"}), 400
    deleted = HoraExtra.query.filter(HoraExtra.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"ok": True, "eliminados": deleted})


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


# ── API: Resumen por contrato (todos los cortes) ─────────────────────────────
@he_bp.route("/api/he/resumen")
@login_required
def api_he_resumen():
    contrato_id = request.args.get("contrato_id", type=int)
    if not contrato_id:
        return jsonify({"ok": False, "msg": "contrato_id requerido"}), 400
    if current_user.rol.lower() == "coordinador":
        if contrato_id not in _ids_contratos_usuario():
            return jsonify({"ok": False, "msg": "No autorizado"}), 403

    q = HoraExtra.query.filter_by(contrato_id=contrato_id)

    def _sum_rep(base):
        return float(base.with_entities(
            db.func.coalesce(db.func.sum(HoraExtra.horas_reportadas), 0)
        ).scalar() or 0)

    def _sum_auth(base):
        return float(base.with_entities(
            db.func.coalesce(db.func.sum(HoraExtra.horas_autorizadas), 0)
        ).scalar() or 0)

    q_conf    = q.filter(HoraExtra.estado == "CONFORME")
    q_noconf  = q.filter(HoraExtra.estado == "NO CONFORME")
    q_desc    = q.filter(HoraExtra.estado == "DESCONTADA")
    total            = q.count()
    hrs_reportadas   = _sum_rep(q)
    conformes        = q_conf.count()
    hrs_autorizadas  = _sum_auth(q_conf)
    hrs_no_autorizadas = _sum_rep(q_noconf)
    hrs_descontadas    = _sum_rep(q_desc)

    # Obtener conceptos reales de la DB (puede ser "3" o "03", lo que sea)
    codigos_db = [
        r[0] for r in
        q.with_entities(HoraExtra.id_concepto).distinct().all()
        if r[0]
    ]
    por_concepto = []
    for codigo in sorted(codigos_db, key=lambda x: x.zfill(4)):
        # Buscar nombre en el dict probando con y sin cero inicial
        nombre = (CONCEPTOS_HE.get(codigo)
                  or CONCEPTOS_HE.get(codigo.zfill(2))
                  or CONCEPTOS_HE.get(codigo.lstrip("0") or "0")
                  or codigo)
        qc       = q.filter(HoraExtra.id_concepto == codigo)
        ct_total = qc.count()
        if ct_total == 0:
            continue
        qc_conf  = qc.filter(HoraExtra.estado == "CONFORME")
        por_concepto.append({
            "codigo":         codigo,
            "nombre":         nombre,
            "total":          ct_total,
            "conformes":      qc_conf.count(),
            "hrs_reportadas": _sum_rep(qc),
            "hrs_autorizadas":_sum_auth(qc_conf),
        })

    try:
        return jsonify({
            "ok": True,
            "total": total,
            "hrs_reportadas":    hrs_reportadas,
            "conformes":         conformes,
            "hrs_autorizadas":   hrs_autorizadas,
            "hrs_no_autorizadas": hrs_no_autorizadas,
            "hrs_descontadas":   hrs_descontadas,
            "por_concepto":      por_concepto,
        })
    except Exception as e:
        import traceback
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500


# ── API: KPIs ────────────────────────────────────────────────────────────────
@he_bp.route("/api/he/kpis")
@login_required
def api_he_kpis():
    q = HoraExtra.query

    # Coordinadores solo ven sus contratos
    if current_user.rol.lower() == "coordinador":
        q = q.filter(HoraExtra.contrato_id.in_(_ids_contratos_usuario()))

    contrato_id = request.args.get("contrato_id", type=int)
    mes         = request.args.get("mes", "")
    corte_id    = request.args.get("corte_id", type=int)
    fecha_desde = request.args.get("fecha_desde", "")
    fecha_hasta = request.args.get("fecha_hasta", "")
    id_concepto = request.args.get("id_concepto", "")

    if contrato_id:
        q = q.filter(HoraExtra.contrato_id == contrato_id)

    if corte_id:
        corte_obj = HeCorte.query.get(corte_id)
        if corte_obj:
            from sqlalchemy import or_ as sa_or
            q = q.filter(sa_or(
                HoraExtra.corte_id == corte_id,
                db.and_(
                    HoraExtra.fecha_labor >= corte_obj.fecha_inicio,
                    HoraExtra.fecha_labor <= corte_obj.fecha_fin,
                )
            ))
        else:
            q = q.filter(HoraExtra.corte_id == corte_id)

    if not corte_id:
        if fecha_desde:
            try:
                q = q.filter(HoraExtra.fecha_labor >= date.fromisoformat(fecha_desde))
            except Exception:
                pass
        if fecha_hasta:
            try:
                q = q.filter(HoraExtra.fecha_labor <= date.fromisoformat(fecha_hasta))
            except Exception:
                pass
    if mes and not fecha_desde and not fecha_hasta:
        try:
            year, month = mes.split("-")
            q = q.filter(
                db.extract("year",  HoraExtra.fecha_labor) == int(year),
                db.extract("month", HoraExtra.fecha_labor) == int(month),
            )
        except Exception:
            pass
    if id_concepto:
        q = q.filter(HoraExtra.id_concepto == id_concepto)

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

    try:
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
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


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
    import traceback
    try:
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
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500


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


@he_bp.route("/api/he/cortes/<int:corte_id>", methods=["DELETE"])
@login_required
def api_he_cortes_eliminar(corte_id):
    import traceback
    try:
        corte = HeCorte.query.get_or_404(corte_id)
        eliminar_registros = request.args.get("eliminar_registros", "false").lower() == "true"
        if eliminar_registros:
            n = HoraExtra.query.filter_by(corte_id=corte_id).delete(synchronize_session=False)
        else:
            n = 0
            HoraExtra.query.filter_by(corte_id=corte_id).update({"corte_id": None}, synchronize_session=False)
        db.session.delete(corte)
        db.session.commit()
        return jsonify({"ok": True, "registros_eliminados": n})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500


@he_bp.route("/api/he/config/verificar-clave", methods=["POST"])
@login_required
def api_he_verificar_clave():
    d = request.get_json() or {}
    clave_enviada = d.get("clave", "")
    password_guardada = HeConfig.get("password_corte_cerrado", "")
    if not password_guardada:
        return jsonify({"ok": True})  # sin contraseña configurada = libre
    ok = clave_enviada == password_guardada
    return jsonify({"ok": ok})


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

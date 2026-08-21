from datetime import datetime, date
from functools import wraps
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.hora_extra import HoraExtra, CONCEPTOS_HE, FACTOR_HE
from app.models.he_concepto import HeConcepto
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
    he.horas_reportadas   = float(f.get("horas_reportadas") or he.horas_reportadas)
    he.horas_compensadas  = float(f.get("horas_compensadas") or 0)
    he.autorizacion_sup   = f.get("autorizacion_sup", he.autorizacion_sup)
    he.justificacion      = f.get("justificacion", he.justificacion)
    he.observacion        = f.get("observacion", he.observacion)
    if f.get("valor_hora")  is not None: he.valor_hora  = f["valor_hora"]
    if f.get("valor_extra") is not None: he.valor_extra = f["valor_extra"]
    # Auto-calcular valor_extra_nomina con horas reportadas
    val_nom = _calc_valor_nomina(he.cedula, he.id_concepto, he.horas_reportadas)
    if val_nom is not None:
        he.valor_extra_nomina = val_nom
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


# ── NEO: página de conciliación ───────────────────────────────────────────────
@he_bp.route("/neo/he-conciliacion")
@login_required
@permiso_requerido("horas_extras")
def he_conciliacion():
    contratos = Contrato.query.filter_by(activo=True).order_by(Contrato.contrato).all()
    return render_template("neo/he_conciliacion.html", contratos=contratos)


def _calc_valor_nomina(cedula, id_concepto, horas):
    """((salario * factor) / 220) * horas — retorna None si no hay salario."""
    if not horas:
        return None
    persona = Persona.query.filter_by(Documento=str(cedula)).first()
    if not persona or not persona.Salario:
        return None
    concepto = HeConcepto.query.filter_by(codigo=str(id_concepto)).first()
    factor = float(concepto.factor) if concepto else FACTOR_HE.get(str(id_concepto), 1.0)
    return round(float(persona.Salario) * factor / 220 * float(horas), 2)


def _parse_hora(val):
    """Extrae HH:MM de strings de hora del Excel (ej. 'Sat Dec 30 1899 05:30:00 GMT...')."""
    if not val:
        return None
    s = str(val).strip()
    # Buscar patrón HH:MM:SS en el string
    import re
    m = re.search(r'(\d{1,2}):(\d{2})(?::\d{2})?', s)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return s[:20] if len(s) > 20 else s or None


# ── API: agregar registros desde conciliación ─────────────────────────────────
@he_bp.route("/api/he/conciliacion-agregar", methods=["POST"])
@login_required
@permiso_requerido("horas_extras")
def api_he_conciliacion_agregar():
    if current_user.rol.lower() not in ("neo", "admin"):
        return jsonify({"ok": False, "msg": "No autorizado"}), 403
    rows = request.get_json(silent=True) or []
    if not rows:
        return jsonify({"ok": False, "msg": "Sin datos"}), 400

    agregados = 0
    errores = []
    try:
        for row in rows:
            contrato_nombre = str(row.get("contrato", "")).strip()
            contrato = Contrato.query.filter(
                Contrato.contrato.ilike(contrato_nombre),
                Contrato.activo == True
            ).first()
            if not contrato:
                # intento coincidencia parcial
                contrato = Contrato.query.filter(
                    Contrato.contrato.ilike(f"%{contrato_nombre}%"),
                    Contrato.activo == True
                ).first()
            if not contrato:
                errores.append(f"Contrato no encontrado: {contrato_nombre}")
                continue

            fecha_str = str(row.get("fecha_labor", "")).strip()
            try:
                fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            except Exception:
                errores.append(f"Fecha inválida: {fecha_str}")
                continue

            cedula = str(row.get("cedula", "")).strip()
            if not cedula:
                errores.append(f"Cédula vacía en fila contrato={contrato_nombre}")
                continue

            id_conc = (lambda v: v.zfill(2) if v else v)(str(row.get("id_concepto", "")).strip())
            hrs_rep = float(row.get("horas_reportadas", 0) or 0)
            he = HoraExtra(
                contrato_id       = contrato.id,
                fecha_labor       = fecha,
                cedula            = cedula,
                nombre            = str(row.get("nombre", "")).strip() or None,
                recurso           = str(row.get("recurso", "")).strip() or None,
                placa             = str(row.get("placa", "")).strip() or None,
                hora_inicio       = _parse_hora(row.get("hora_inicio")),
                hora_fin          = _parse_hora(row.get("hora_fin")),
                id_concepto       = id_conc,
                horas_reportadas  = hrs_rep,
                horas_compensadas = float(row.get("horas_compensadas", 0) or 0),
                tipo_he           = str(row.get("tipo_he", "")).strip() or None,
                justificacion     = str(row.get("justificacion", "")).strip() or None,
                observacion       = str(row.get("observacion", "")).strip() or None,
                corte_id          = int(row["corte_id"]) if row.get("corte_id") else None,
                reportado_por_id  = current_user.id,
                estado            = "PENDIENTE",
                valor_extra_nomina = _calc_valor_nomina(cedula, id_conc, hrs_rep),
            )
            db.session.add(he)
            agregados += 1

        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        return jsonify({"ok": False, "msg": str(ex)}), 500

    return jsonify({"ok": True, "agregados": agregados, "errores": errores})


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

    from sqlalchemy import case as sa_case, func as sa_func
    try:
        row = q.with_entities(
            sa_func.count().label("total"),
            sa_func.sum(sa_case((HoraExtra.estado == "PENDIENTE",   1), else_=0)).label("pendientes"),
            sa_func.sum(sa_case((HoraExtra.estado == "CONFORME",    1), else_=0)).label("conformes"),
            sa_func.sum(sa_case((HoraExtra.estado == "NO CONFORME", 1), else_=0)).label("no_conformes"),
            sa_func.sum(sa_case((HoraExtra.estado == "DESCONTADA",  1), else_=0)).label("descontadas"),
            sa_func.coalesce(sa_func.sum(HoraExtra.horas_reportadas), 0).label("hrs_rep"),
            sa_func.coalesce(sa_func.sum(HoraExtra.horas_autorizadas), 0).label("hrs_auth"),
            sa_func.coalesce(sa_func.sum(sa_case((HoraExtra.estado == "CONFORME",    HoraExtra.horas_reportadas), else_=0)), 0).label("hrs_conf"),
            sa_func.coalesce(sa_func.sum(sa_case((HoraExtra.estado == "NO CONFORME", HoraExtra.horas_reportadas), else_=0)), 0).label("hrs_noconf"),
            sa_func.coalesce(sa_func.sum(sa_case((HoraExtra.estado == "DESCONTADA",  HoraExtra.horas_reportadas), else_=0)), 0).label("hrs_desc"),
            sa_func.coalesce(sa_func.sum(sa_case((HoraExtra.estado == "PENDIENTE",   HoraExtra.horas_reportadas), else_=0)), 0).label("hrs_pend"),
        ).one()
        return jsonify({
            "total":            row.total,
            "pendientes":       row.pendientes,
            "conformes":        row.conformes,
            "no_conformes":     row.no_conformes,
            "descontadas":      row.descontadas,
            "hrs_reportadas":   float(row.hrs_rep),
            "hrs_conformes":    float(row.hrs_conf),
            "hrs_no_conformes": float(row.hrs_noconf),
            "hrs_descontadas":  float(row.hrs_desc),
            "hrs_pendientes":   float(row.hrs_pend),
            "hrs_autorizadas":  float(row.hrs_auth),
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


# ── API: ranking de contratos por horas ──────────────────────────────────────
@he_bp.route("/api/he/ranking-contratos")
@login_required
def api_he_ranking_contratos():
    from sqlalchemy import func as sa_func, or_ as sa_or
    from app.models.hora_extra import CONCEPTOS_HE

    corte_id    = request.args.get("corte_id", type=int)
    fecha_desde = request.args.get("fecha_desde", "")
    fecha_hasta = request.args.get("fecha_hasta", "")

    q = db.session.query(
        HoraExtra.contrato_id,
        HoraExtra.id_concepto,
        HoraExtra.cedula,
        HoraExtra.nombre,
        sa_func.sum(HoraExtra.horas_reportadas).label("hrs"),
        sa_func.sum(HoraExtra.horas_autorizadas).label("hrs_auth"),
    )

    if corte_id:
        corte_obj = HeCorte.query.get(corte_id)
        if corte_obj:
            q = q.filter(sa_or(
                HoraExtra.corte_id == corte_id,
                db.and_(
                    HoraExtra.fecha_labor >= corte_obj.fecha_inicio,
                    HoraExtra.fecha_labor <= corte_obj.fecha_fin,
                )
            ))
    else:
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

    rows = q.group_by(
        HoraExtra.contrato_id, HoraExtra.id_concepto, HoraExtra.cedula, HoraExtra.nombre
    ).all()

    # Construir jerarquía: contrato → concepto → técnico
    contratos_map = {}
    for contrato_id_val, concepto, cedula, nombre, hrs, hrs_auth in rows:
        contrato_obj = Contrato.query.get(contrato_id_val)
        if not contrato_obj:
            continue
        nombre_contrato = contrato_obj.contrato
        hrs_f      = float(hrs or 0)
        hrs_auth_f = float(hrs_auth or 0)

        if nombre_contrato not in contratos_map:
            contratos_map[nombre_contrato] = {"nombre": nombre_contrato, "hrs": 0, "hrs_auth": 0, "conceptos": {}}
        contratos_map[nombre_contrato]["hrs"]      += hrs_f
        contratos_map[nombre_contrato]["hrs_auth"] += hrs_auth_f

        concepto_pad = (concepto or "").strip().zfill(2) if concepto else ""
        tipo = CONCEPTOS_HE.get(concepto_pad, concepto_pad)
        clave_conc = concepto_pad
        if clave_conc not in contratos_map[nombre_contrato]["conceptos"]:
            contratos_map[nombre_contrato]["conceptos"][clave_conc] = {
                "concepto": concepto_pad, "tipo": tipo, "hrs": 0, "hrs_auth": 0, "tecnicos": []
            }
        contratos_map[nombre_contrato]["conceptos"][clave_conc]["hrs"]      += hrs_f
        contratos_map[nombre_contrato]["conceptos"][clave_conc]["hrs_auth"] += hrs_auth_f
        tecs = contratos_map[nombre_contrato]["conceptos"][clave_conc]["tecnicos"]
        tec_key = cedula or ""
        existing = next((t for t in tecs if t["cedula"] == tec_key), None)
        if existing:
            existing["hrs"]      += hrs_f
            existing["hrs_auth"] += hrs_auth_f
        else:
            tecs.append({"cedula": tec_key, "nombre": nombre or "", "hrs": hrs_f, "hrs_auth": hrs_auth_f})

    # Convertir a lista ordenada
    result = []
    for c in sorted(contratos_map.values(), key=lambda x: x["hrs"], reverse=True):
        conceptos = sorted(c["conceptos"].values(), key=lambda x: x["hrs"], reverse=True)
        for conc in conceptos:
            conc["tecnicos"] = sorted(conc["tecnicos"], key=lambda x: x["hrs"], reverse=True)[:10]
        c["conceptos"] = conceptos
        result.append(c)

    return jsonify(result)


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


# ── HE Conceptos CRUD ────────────────────────────────────────────────────────

@he_bp.route("/neo/he-conceptos")
@login_required
def page_he_conceptos():
    return render_template("neo/he_conceptos.html")


@he_bp.route("/api/he/conceptos", methods=["GET"])
@login_required
def api_he_conceptos_list():
    items = HeConcepto.query.order_by(HeConcepto.codigo).all()
    return jsonify([c.to_dict() for c in items])


@he_bp.route("/api/he/conceptos", methods=["POST"])
@login_required
def api_he_conceptos_create():
    data = request.get_json(force=True)
    codigo = str(data.get("codigo", "")).strip().zfill(2) if data.get("codigo") else None
    if not codigo or not data.get("nombre") or data.get("factor") is None:
        return jsonify({"error": "codigo, nombre y factor son requeridos"}), 400
    if HeConcepto.query.filter_by(codigo=codigo).first():
        return jsonify({"error": f"Ya existe concepto con código {codigo}"}), 409
    c = HeConcepto(
        codigo=codigo,
        nombre=str(data["nombre"]).strip(),
        factor=float(data["factor"]),
        activo=bool(data.get("activo", True)),
    )
    db.session.add(c)
    db.session.commit()
    return jsonify(c.to_dict()), 201


@he_bp.route("/api/he/conceptos/<int:cid>", methods=["PUT"])
@login_required
def api_he_conceptos_update(cid):
    c = HeConcepto.query.get_or_404(cid)
    data = request.get_json(force=True)
    if "codigo" in data:
        c.codigo = str(data["codigo"]).strip().zfill(2)
    if "nombre" in data:
        c.nombre = str(data["nombre"]).strip()
    if "factor" in data:
        c.factor = float(data["factor"])
    if "activo" in data:
        c.activo = bool(data["activo"])
    db.session.commit()
    return jsonify(c.to_dict())


@he_bp.route("/api/he/conceptos/<int:cid>", methods=["DELETE"])
@login_required
def api_he_conceptos_delete(cid):
    c = HeConcepto.query.get_or_404(cid)
    db.session.delete(c)
    db.session.commit()
    return jsonify({"ok": True})


# ── API: valor extra nómina agrupado contrato→tipo→técnico ───────────────────

@he_bp.route("/api/he/valor-extra-nomina")
@login_required
def api_he_valor_extra_nomina():
    params = request.args
    q = HoraExtra.query
    if params.get("contrato_id"):
        q = q.filter(HoraExtra.contrato_id == int(params["contrato_id"]))
    if params.get("corte_id"):
        q = q.filter(HoraExtra.corte_id == int(params["corte_id"]))
    if params.get("mes"):
        y, m = params["mes"].split("-")
        q = q.filter(db.extract("year", HoraExtra.fecha_labor) == int(y),
                     db.extract("month", HoraExtra.fecha_labor) == int(m))
    if params.get("fecha_desde"):
        q = q.filter(HoraExtra.fecha_labor >= date.fromisoformat(params["fecha_desde"]))
    if params.get("fecha_hasta"):
        q = q.filter(HoraExtra.fecha_labor <= date.fromisoformat(params["fecha_hasta"]))

    registros = q.all()

    # Cargar salarios y factores en memoria para eficiencia
    cedulas = {r.cedula for r in registros}
    salarios = {p.Documento: float(p.Salario)
                for p in Persona.query.filter(Persona.Documento.in_(cedulas), Persona.Salario.isnot(None)).all()}
    factores = {c.codigo: float(c.factor) for c in HeConcepto.query.all()}

    def val(cedula, id_concepto, horas):
        if not horas:
            return 0
        sal = salarios.get(cedula)
        if not sal:
            return 0
        fac = factores.get(str(id_concepto), FACTOR_HE.get(str(id_concepto), 1.0))
        return round(sal * fac / 220 * float(horas), 2)

    contratos = {}
    for r in registros:
        cid = r.contrato_id
        cname = r.contrato.contrato if r.contrato else ""
        if cid not in contratos:
            contratos[cid] = {"nombre": cname, "contrato_id": cid,
                               "valor_rep": 0, "valor_auth": 0, "conceptos": {}}

        vr = val(r.cedula, r.id_concepto, r.horas_reportadas)
        va = val(r.cedula, r.id_concepto, r.horas_autorizadas) if r.horas_autorizadas else 0

        contratos[cid]["valor_rep"]  += vr
        contratos[cid]["valor_auth"] += va

        ck = r.id_concepto or ""
        if ck not in contratos[cid]["conceptos"]:
            contratos[cid]["conceptos"][ck] = {
                "codigo": ck,
                "tipo": r.tipo_he or CONCEPTOS_HE.get(ck, ck),
                "valor_rep": 0, "valor_auth": 0, "tecnicos": {}
            }
        contratos[cid]["conceptos"][ck]["valor_rep"]  += vr
        contratos[cid]["conceptos"][ck]["valor_auth"] += va

        tk = r.cedula
        tecs = contratos[cid]["conceptos"][ck]["tecnicos"]
        if tk not in tecs:
            tecs[tk] = {"cedula": tk, "nombre": r.nombre or "", "valor_rep": 0, "valor_auth": 0}
        tecs[tk]["valor_rep"]  += vr
        tecs[tk]["valor_auth"] += va

    result = []
    for c in sorted(contratos.values(), key=lambda x: -x["valor_rep"]):
        c["conceptos"] = sorted(
            [dict(v, tecnicos=sorted(v["tecnicos"].values(), key=lambda t: -t["valor_rep"]))
             for v in c["conceptos"].values()],
            key=lambda x: -x["valor_rep"]
        )
        result.append(c)

    return jsonify(result)


# ── API: recalcular valor_extra_nomina en todos los registros ────────────────

@he_bp.route("/api/he/diagnostico-valores")
@login_required
def api_he_diagnostico_valores():
    """Retorna por qué registros no tienen valor_extra_nomina calculado."""
    if current_user.rol.lower() not in ("neo", "admin"):
        return jsonify({"ok": False, "msg": "No autorizado"}), 403

    salarios = {p.Documento: float(p.Salario) if p.Salario else None
                for p in Persona.query.all()}
    factores = {c.codigo: float(c.factor) for c in HeConcepto.query.all()}

    sin_valor = HoraExtra.query.filter(HoraExtra.valor_extra_nomina.is_(None)).all()

    razones = {"sin_salario_en_personas": [], "salario_nulo": [], "sin_horas": [], "sin_concepto": []}
    total = len(sin_valor)

    cedulas_sin_persona = set()
    cedulas_sin_salario = set()

    for he in sin_valor:
        if not he.horas_reportadas:
            razones["sin_horas"].append(he.id)
            continue
        if he.cedula not in salarios:
            cedulas_sin_persona.add(he.cedula)
            razones["sin_salario_en_personas"].append(he.cedula)
        elif not salarios[he.cedula]:
            cedulas_sin_salario.add(he.cedula)
            razones["salario_nulo"].append(he.cedula)

    return jsonify({
        "total_sin_valor": total,
        "sin_horas_reportadas": len(razones["sin_horas"]),
        "cedulas_sin_persona_en_bd": sorted(cedulas_sin_persona),
        "cedulas_con_salario_nulo": sorted(cedulas_sin_salario),
        "resumen": {
            "sin_persona": len(cedulas_sin_persona),
            "salario_nulo": len(cedulas_sin_salario),
            "sin_horas": len(razones["sin_horas"]),
        }
    })


@he_bp.route("/api/he/normalizar-conceptos", methods=["POST"])
@login_required
def api_he_normalizar_conceptos():
    """Rellena id_concepto con cero a la izquierda: '3' → '03'."""
    if current_user.rol.lower() not in ("neo", "admin"):
        return jsonify({"ok": False, "msg": "No autorizado"}), 403
    registros = HoraExtra.query.filter(
        db.func.length(HoraExtra.id_concepto) < 2
    ).all()
    actualizados = 0
    for he in registros:
        if he.id_concepto:
            he.id_concepto = he.id_concepto.strip().zfill(2)
            he.tipo_he = CONCEPTOS_HE.get(he.id_concepto, he.tipo_he)
            actualizados += 1
    db.session.commit()
    return jsonify({"ok": True, "actualizados": actualizados})


@he_bp.route("/api/he/recalcular-valores", methods=["POST"])
@login_required
def api_he_recalcular_valores():
    if current_user.rol.lower() not in ("neo", "admin"):
        return jsonify({"ok": False, "msg": "No autorizado"}), 403
    salarios = {p.Documento: float(p.Salario)
                for p in Persona.query.filter(Persona.Salario.isnot(None)).all()}
    factores = {c.codigo: float(c.factor) for c in HeConcepto.query.all()}
    actualizados = 0
    for he in HoraExtra.query.all():
        sal = salarios.get(he.cedula)
        if not sal or not he.horas_reportadas:
            continue
        fac = factores.get(he.id_concepto, FACTOR_HE.get(he.id_concepto, 1.0))
        he.valor_extra_nomina = round(sal * fac / 220 * float(he.horas_reportadas), 2)
        actualizados += 1
    db.session.commit()
    return jsonify({"ok": True, "actualizados": actualizados})

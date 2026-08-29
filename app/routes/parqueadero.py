from datetime import datetime, date
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models.parqueadero import ParqueaderoRegistro

park_bp = Blueprint("parqueadero", __name__)

TARIFA_CARRO_PRIMERA  = 5000
TARIFA_CARRO_ADICIONAL= 3000
TARIFA_MOTO           = 5000
TARIFA_CASCO          = 2000


def _requiere_parqueadero():
    if current_user.rol.lower() not in ("parqueadero", "admin_parqueadero", "admin"):
        abort(403)


def _calcular_valor(tipo, hora_ingreso, cascos, hora_salida=None):
    fin = hora_salida or datetime.utcnow()
    minutos = max(1, int((fin - hora_ingreso).total_seconds() / 60))
    if tipo == "moto":
        return TARIFA_MOTO + cascos * TARIFA_CASCO
    # carro: primera hora + adicionales, fracción cuenta como hora completa
    import math
    horas = math.ceil(minutos / 60)
    if horas <= 1:
        return TARIFA_CARRO_PRIMERA
    return TARIFA_CARRO_PRIMERA + (horas - 1) * TARIFA_CARRO_ADICIONAL


# ── Páginas ──────────────────────────────────────────────────────────────────

@park_bp.route("/parqueadero")
@login_required
def operador():
    _requiere_parqueadero()
    return render_template("parqueadero/operador.html")


@park_bp.route("/parqueadero/admin")
@login_required
def admin():
    if current_user.rol.lower() not in ("admin_parqueadero", "admin"):
        abort(403)
    return render_template("parqueadero/admin_park.html")


# ── API ───────────────────────────────────────────────────────────────────────

@park_bp.route("/api/parqueadero/activos")
@login_required
def api_activos():
    _requiere_parqueadero()
    registros = ParqueaderoRegistro.query.filter_by(estado="activo").order_by(ParqueaderoRegistro.hora_ingreso).all()
    ahora = datetime.utcnow()
    resultado = []
    for r in registros:
        d = r.to_dict()
        d["valor_actual"] = _calcular_valor(r.tipo, r.hora_ingreso, r.cascos)
        resultado.append(d)
    return jsonify(resultado)


@park_bp.route("/api/parqueadero/placa/<placa>")
@login_required
def api_consultar_placa(placa):
    _requiere_parqueadero()
    placa = placa.upper().strip()
    registro = ParqueaderoRegistro.query.filter_by(placa=placa, estado="activo").first()
    if not registro:
        return jsonify({"activo": False})
    d = registro.to_dict()
    d["activo"] = True
    d["valor_actual"] = _calcular_valor(registro.tipo, registro.hora_ingreso, registro.cascos)
    return jsonify(d)


@park_bp.route("/api/parqueadero/ingresar", methods=["POST"])
@login_required
def api_ingresar():
    _requiere_parqueadero()
    data  = request.get_json(silent=True) or {}
    placa = str(data.get("placa", "")).upper().strip()
    tipo  = str(data.get("tipo", "")).lower()
    cascos= int(data.get("cascos", 0))

    if not placa or tipo not in ("carro", "moto"):
        return jsonify({"ok": False, "msg": "Datos inválidos"}), 400

    existente = ParqueaderoRegistro.query.filter_by(placa=placa, estado="activo").first()
    if existente:
        return jsonify({"ok": False, "msg": "La placa ya tiene un ingreso activo"}), 409

    ahora = datetime.utcnow()
    r = ParqueaderoRegistro(
        placa=placa, tipo=tipo, hora_ingreso=ahora,
        cascos=cascos if tipo == "moto" else 0,
        estado="activo", fecha=ahora.date()
    )
    db.session.add(r)
    db.session.commit()
    return jsonify({"ok": True, "registro": r.to_dict()})


@park_bp.route("/api/parqueadero/salir/<int:id>", methods=["POST"])
@login_required
def api_salir(id):
    _requiere_parqueadero()
    r = ParqueaderoRegistro.query.get_or_404(id)
    if r.estado != "activo":
        return jsonify({"ok": False, "msg": "El registro ya fue cerrado"}), 400

    data   = request.get_json(silent=True) or {}
    cascos = int(data.get("cascos", r.cascos))

    ahora = datetime.utcnow()
    r.hora_salida = ahora
    r.cascos      = cascos
    r.valor_total = _calcular_valor(r.tipo, r.hora_ingreso, cascos, ahora)
    r.estado      = "finalizado"
    db.session.commit()
    return jsonify({"ok": True, "registro": r.to_dict(), "valor_total": r.valor_total})


@park_bp.route("/api/parqueadero/historial")
@login_required
def api_historial():
    _requiere_parqueadero()
    fecha_str = request.args.get("fecha", date.today().isoformat())
    try:
        fecha = date.fromisoformat(fecha_str)
    except Exception:
        fecha = date.today()
    registros = ParqueaderoRegistro.query.filter_by(
        estado="finalizado", fecha=fecha
    ).order_by(ParqueaderoRegistro.hora_salida.desc()).all()
    return jsonify([r.to_dict() for r in registros])


@park_bp.route("/api/parqueadero/stats")
@login_required
def api_stats():
    _requiere_parqueadero()
    hoy = date.today()
    activos   = ParqueaderoRegistro.query.filter_by(estado="activo").count()
    salidas   = ParqueaderoRegistro.query.filter_by(estado="finalizado", fecha=hoy).count()
    recaudo   = db.session.query(
        db.func.coalesce(db.func.sum(ParqueaderoRegistro.valor_total), 0)
    ).filter_by(estado="finalizado", fecha=hoy).scalar() or 0
    return jsonify({"activos": activos, "salidas": salidas, "recaudo": float(recaudo)})


@park_bp.route("/api/parqueadero/nuevo-dia", methods=["POST"])
@login_required
def api_nuevo_dia():
    if current_user.rol.lower() not in ("admin_parqueadero", "admin"):
        abort(403)
    hoy = date.today()
    eliminados = ParqueaderoRegistro.query.filter(
        ParqueaderoRegistro.estado == "finalizado",
        ParqueaderoRegistro.fecha < hoy
    ).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"ok": True, "eliminados": eliminados})


@park_bp.route("/api/parqueadero/actualizar-cascos/<int:id>", methods=["POST"])
@login_required
def api_actualizar_cascos(id):
    _requiere_parqueadero()
    r = ParqueaderoRegistro.query.get_or_404(id)
    if r.estado != "activo":
        return jsonify({"ok": False, "msg": "Registro ya cerrado"}), 400
    data   = request.get_json(silent=True) or {}
    r.cascos = max(0, int(data.get("cascos", r.cascos)))
    db.session.commit()
    return jsonify({"ok": True, "cascos": r.cascos})

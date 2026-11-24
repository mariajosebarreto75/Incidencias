"""
Módulo Parqueadero — mensualidades, pagos, salidas, alertas y reportes.
"""
from calendar import monthrange
from datetime import date, datetime

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify, abort)
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.models.parq_cliente import ParqCliente
from app.models.parq_pago    import ParqPago
from app.models.parq_salida  import ParqSalida
from app.models.parq_cierre  import ParqCierre
from app.models.parq_tarifa  import ParqTarifa

parq_bp = Blueprint("parqueadero", __name__, url_prefix="/parqueadero")

# ── helpers de permiso ────────────────────────────────────────────────────────

def _require(permiso):
    """Aborta con 403 si el usuario no tiene el permiso indicado."""
    if not current_user.tiene_permiso(permiso):
        abort(403)

# ── lógica de estado del cliente ──────────────────────────────────────────────

def _dia_corte_real(dia: int, anio: int, mes: int) -> int:
    """Devuelve el día real de corte ajustado al último día del mes si es necesario."""
    return min(dia, monthrange(anio, mes)[1])

def estado_cliente(cliente: ParqCliente, hoy: date = None) -> dict:
    """
    Calcula el estado de pago del cliente para el mes actual.
    Retorna dict con 'estado' (al_dia|por_vencer|vencido), 'dias_mora', 'color'.
    """
    if hoy is None:
        hoy = date.today()

    anio, mes = hoy.year, hoy.month
    mes_str = f"{anio}-{mes:02d}"

    # Verificar si ya pagó el mes completo (mensualidad registrada)
    pago = ParqPago.query.filter_by(
        cliente_id=cliente.id,
        concepto="mensualidad",
        mes_pagado=mes_str,
        eliminado=False,
    ).first()

    if pago:
        return {"estado": "al_dia", "dias_mora": 0, "color": "verde",
                "label": "Al día", "badge": "success"}

    corte = _dia_corte_real(cliente.dia_corte, anio, mes)
    fecha_corte = date(anio, mes, corte)
    dias_antes = (fecha_corte - hoy).days

    if hoy > fecha_corte:
        dias_mora = (hoy - fecha_corte).days
        return {"estado": "vencido", "dias_mora": dias_mora, "color": "rojo",
                "label": f"Vencido ({dias_mora}d)", "badge": "danger"}

    if dias_antes <= 5:
        return {"estado": "por_vencer", "dias_mora": 0, "color": "amarillo",
                "label": "Por vencer", "badge": "warning"}

    return {"estado": "al_dia", "dias_mora": 0, "color": "verde",
            "label": "Al día", "badge": "success"}


def _cop(valor) -> str:
    """Formatea un número como pesos colombianos: $150.000"""
    if valor is None:
        return "$0"
    return f"${int(valor):,}".replace(",", ".")


# ── seed de tarifas por defecto ───────────────────────────────────────────────

def seed_tarifas():
    """Inserta tarifas por defecto si la tabla está vacía."""
    if ParqTarifa.query.count() == 0:
        db.session.add_all([
            ParqTarifa(tipo_vehiculo="carro", valor=150000, actualizado_por="sistema"),
            ParqTarifa(tipo_vehiculo="moto",  valor=80000,  actualizado_por="sistema"),
        ])
        db.session.commit()


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@parq_bp.route("/")
@login_required
def dashboard():
    _require("parqueadero.ver")

    hoy = date.today()
    mes_param = request.args.get("mes", f"{hoy.year}-{hoy.month:02d}")
    try:
        anio_sel, mes_sel = int(mes_param[:4]), int(mes_param[5:7])
    except (ValueError, IndexError):
        anio_sel, mes_sel = hoy.year, hoy.month
    mes_str = f"{anio_sel}-{mes_sel:02d}"

    # Ingresos del mes (pagos no eliminados)
    pagos_mes = ParqPago.query.filter(
        ParqPago.eliminado == False,
        func.to_char(ParqPago.fecha_pago, "YYYY-MM") == mes_str
    ).all()
    total_ingresos    = sum(float(p.valor) for p in pagos_mes)
    total_efectivo    = sum(float(p.valor) for p in pagos_mes if p.medio == "efectivo")
    total_transf      = sum(float(p.valor) for p in pagos_mes if p.medio == "transferencia")

    # Salidas del mes
    salidas_mes = ParqSalida.query.filter(
        ParqSalida.eliminado == False,
        func.to_char(ParqSalida.fecha, "YYYY-MM") == mes_str
    ).all()
    total_salidas = sum(float(s.valor) for s in salidas_mes)
    utilidad      = total_ingresos - total_salidas

    # Estados de clientes activos
    clientes_activos = ParqCliente.query.filter_by(activo=True).all()
    conteos = {"al_dia": 0, "por_vencer": 0, "vencido": 0}
    for c in clientes_activos:
        est = estado_cliente(c, hoy)["estado"]
        conteos[est] = conteos.get(est, 0) + 1

    # Cierre de caja del día
    cierre_hoy = ParqCierre.query.filter_by(fecha=hoy).first()

    # Últimos movimientos (5 pagos + 5 salidas mezclados)
    ultimos_pagos = ParqPago.query.filter_by(eliminado=False)\
        .order_by(ParqPago.creado_en.desc()).limit(8).all()
    ultimas_salidas = ParqSalida.query.filter_by(eliminado=False)\
        .order_by(ParqSalida.creado_en.desc()).limit(8).all()
    movimientos = sorted(
        [{"tipo": "ingreso", "desc": f"{p.concepto.title()} – {p.cliente.nombre if p.cliente else 'Ocasional'}",
          "valor": float(p.valor), "medio": p.medio, "fecha": p.fecha_pago} for p in ultimos_pagos] +
        [{"tipo": "salida",  "desc": f"{s.categoria.replace('_',' ').title()} – {s.descripcion[:40]}",
          "valor": float(s.valor), "medio": s.medio, "fecha": s.fecha} for s in ultimas_salidas],
        key=lambda x: x["fecha"], reverse=True
    )[:10]

    # Gráfica últimos 6 meses
    meses_graf = []
    for i in range(5, -1, -1):
        m = mes_sel - i
        a = anio_sel
        while m <= 0:
            m += 12; a -= 1
        ms = f"{a}-{m:02d}"
        ing = db.session.query(func.coalesce(func.sum(ParqPago.valor), 0)).filter(
            ParqPago.eliminado == False,
            func.to_char(ParqPago.fecha_pago, "YYYY-MM") == ms
        ).scalar()
        sal = db.session.query(func.coalesce(func.sum(ParqSalida.valor), 0)).filter(
            ParqSalida.eliminado == False,
            func.to_char(ParqSalida.fecha, "YYYY-MM") == ms
        ).scalar()
        meses_graf.append({"mes": ms, "ingresos": float(ing), "salidas": float(sal)})

    return render_template("parqueadero/dashboard.html",
        mes_str=mes_str, hoy=hoy,
        total_ingresos=total_ingresos, total_efectivo=total_efectivo,
        total_transf=total_transf, total_salidas=total_salidas, utilidad=utilidad,
        conteos=conteos, cierre_hoy=cierre_hoy,
        movimientos=movimientos, meses_graf=meses_graf,
        total_clientes=len(clientes_activos), cop=_cop,
    )


# ── CLIENTES ──────────────────────────────────────────────────────────────────

@parq_bp.route("/clientes")
@login_required
def clientes():
    _require("parqueadero.ver")

    q      = request.args.get("q", "").strip()
    estado = request.args.get("estado", "")
    tipo   = request.args.get("tipo", "")
    hoy    = date.today()

    query = ParqCliente.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(ParqCliente.nombre.ilike(like), ParqCliente.placa.ilike(like))
        )
    if tipo:
        query = query.filter_by(tipo_vehiculo=tipo)
    # Filtro de activo: por defecto muestra solo activos
    mostrar_inactivos = request.args.get("inactivos") == "1"
    if not mostrar_inactivos:
        query = query.filter_by(activo=True)

    todos = query.order_by(ParqCliente.nombre).all()

    # Calcular estado de cada cliente
    lista = []
    for c in todos:
        est = estado_cliente(c, hoy)
        if estado and est["estado"] != estado:
            continue
        lista.append({"cliente": c, "estado": est})

    tarifas = {t.tipo_vehiculo: float(t.valor) for t in ParqTarifa.query.all()}

    return render_template("parqueadero/clientes.html",
        lista=lista, q=q, estado_filtro=estado, tipo_filtro=tipo,
        mostrar_inactivos=mostrar_inactivos, tarifas=tarifas, cop=_cop,
    )


@parq_bp.route("/clientes/nuevo", methods=["GET", "POST"])
@login_required
def nuevo_cliente():
    _require("parqueadero.clientes")

    tarifas = {t.tipo_vehiculo: float(t.valor) for t in ParqTarifa.query.all()}

    if request.method == "POST":
        placa = request.form.get("placa", "").strip().upper()
        if ParqCliente.query.filter_by(placa=placa).first():
            flash(f"Ya existe un cliente con la placa {placa}.", "danger")
            return redirect(url_for("parqueadero.nuevo_cliente"))

        try:
            dia_corte = int(request.form.get("dia_corte", 1))
            assert 1 <= dia_corte <= 31
        except (ValueError, AssertionError):
            flash("El día de corte debe ser entre 1 y 31.", "danger")
            return redirect(url_for("parqueadero.nuevo_cliente"))

        c = ParqCliente(
            nombre         = request.form.get("nombre", "").strip(),
            cedula         = request.form.get("cedula", "").strip() or None,
            telefono       = request.form.get("telefono", "").strip() or None,
            placa          = placa,
            tipo_vehiculo  = request.form.get("tipo_vehiculo"),
            tarifa_mensual = float(request.form.get("tarifa_mensual", 0)),
            dia_corte      = dia_corte,
            fecha_inicio   = date.fromisoformat(request.form.get("fecha_inicio")),
            observaciones  = request.form.get("observaciones", "").strip() or None,
            creado_por     = current_user.username,
        )
        db.session.add(c)
        db.session.commit()
        flash(f"Cliente {c.nombre} registrado correctamente.", "success")
        return redirect(url_for("parqueadero.clientes"))

    return render_template("parqueadero/form_cliente.html",
        cliente=None, tarifas=tarifas, cop=_cop,
        titulo="Nuevo cliente", accion=url_for("parqueadero.nuevo_cliente"),
    )


@parq_bp.route("/clientes/<int:cid>/editar", methods=["GET", "POST"])
@login_required
def editar_cliente(cid):
    _require("parqueadero.clientes")
    c = ParqCliente.query.get_or_404(cid)
    tarifas = {t.tipo_vehiculo: float(t.valor) for t in ParqTarifa.query.all()}

    if request.method == "POST":
        placa_nueva = request.form.get("placa", "").strip().upper()
        existente = ParqCliente.query.filter(
            ParqCliente.placa == placa_nueva, ParqCliente.id != cid
        ).first()
        if existente:
            flash(f"La placa {placa_nueva} ya está registrada.", "danger")
            return redirect(url_for("parqueadero.editar_cliente", cid=cid))

        try:
            dia_corte = int(request.form.get("dia_corte", 1))
            assert 1 <= dia_corte <= 31
        except (ValueError, AssertionError):
            flash("El día de corte debe ser entre 1 y 31.", "danger")
            return redirect(url_for("parqueadero.editar_cliente", cid=cid))

        c.nombre         = request.form.get("nombre", "").strip()
        c.cedula         = request.form.get("cedula", "").strip() or None
        c.telefono       = request.form.get("telefono", "").strip() or None
        c.placa          = placa_nueva
        c.tipo_vehiculo  = request.form.get("tipo_vehiculo")
        c.tarifa_mensual = float(request.form.get("tarifa_mensual", 0))
        c.dia_corte      = dia_corte
        c.fecha_inicio   = date.fromisoformat(request.form.get("fecha_inicio"))
        c.observaciones  = request.form.get("observaciones", "").strip() or None
        db.session.commit()
        flash("Cliente actualizado.", "success")
        return redirect(url_for("parqueadero.clientes"))

    return render_template("parqueadero/form_cliente.html",
        cliente=c, tarifas=tarifas, cop=_cop,
        titulo="Editar cliente", accion=url_for("parqueadero.editar_cliente", cid=cid),
    )


@parq_bp.route("/clientes/<int:cid>/desactivar", methods=["POST"])
@login_required
def desactivar_cliente(cid):
    _require("parqueadero.clientes")
    c = ParqCliente.query.get_or_404(cid)
    c.activo = not c.activo
    db.session.commit()
    estado_txt = "activado" if c.activo else "desactivado"
    flash(f"Cliente {c.nombre} {estado_txt}.", "success")
    return redirect(url_for("parqueadero.clientes"))


@parq_bp.route("/clientes/<int:cid>/historial")
@login_required
def historial_cliente(cid):
    _require("parqueadero.ver")
    c    = ParqCliente.query.get_or_404(cid)
    hoy  = date.today()
    est  = estado_cliente(c, hoy)
    pagos = ParqPago.query.filter_by(cliente_id=cid, eliminado=False)\
        .order_by(ParqPago.fecha_pago.desc()).all()
    return render_template("parqueadero/historial_cliente.html",
        cliente=c, pagos=pagos, est=est, hoy=hoy, cop=_cop,
    )


# ── PAGOS ─────────────────────────────────────────────────────────────────────

@parq_bp.route("/pagos")
@login_required
def pagos():
    _require("parqueadero.ver")

    hoy       = date.today()
    mes_param = request.args.get("mes", f"{hoy.year}-{hoy.month:02d}")
    medio_f   = request.args.get("medio", "")
    concepto_f = request.args.get("concepto", "")

    query = ParqPago.query.filter(
        ParqPago.eliminado == False,
        func.to_char(ParqPago.fecha_pago, "YYYY-MM") == mes_param,
    )
    if medio_f:
        query = query.filter_by(medio=medio_f)
    if concepto_f:
        query = query.filter_by(concepto=concepto_f)

    lista = query.order_by(ParqPago.fecha_pago.desc()).all()
    total = sum(float(p.valor) for p in lista)

    clientes_activos = ParqCliente.query.filter_by(activo=True)\
        .order_by(ParqCliente.nombre).all()

    return render_template("parqueadero/pagos.html",
        lista=lista, total=total, mes_param=mes_param,
        medio_f=medio_f, concepto_f=concepto_f,
        clientes_activos=clientes_activos, hoy=hoy, cop=_cop,
    )


@parq_bp.route("/pagos/registrar", methods=["POST"])
@login_required
def registrar_pago():
    _require("parqueadero.pagos")

    concepto = request.form.get("concepto")
    medio    = request.form.get("medio")
    entidad  = request.form.get("entidad", "").strip() or None
    if medio == "transferencia" and not entidad:
        flash("Para transferencia, la entidad es obligatoria.", "danger")
        return redirect(url_for("parqueadero.pagos"))

    try:
        valor = float(request.form.get("valor", 0))
        assert valor > 0
    except (ValueError, AssertionError):
        flash("El valor debe ser mayor a cero.", "danger")
        return redirect(url_for("parqueadero.pagos"))

    cliente_id = request.form.get("cliente_id") or None
    if cliente_id:
        cliente_id = int(cliente_id)

    p = ParqPago(
        cliente_id     = cliente_id,
        concepto       = concepto,
        mes_pagado     = request.form.get("mes_pagado") or None,
        valor          = valor,
        fecha_pago     = date.fromisoformat(request.form.get("fecha_pago")),
        medio          = medio,
        entidad        = entidad,
        referencia     = request.form.get("referencia", "").strip() or None,
        registrado_por = current_user.username,
    )
    db.session.add(p)
    db.session.commit()
    flash("Pago registrado correctamente.", "success")
    return redirect(url_for("parqueadero.pagos",
        mes=request.form.get("mes_pagado", f"{date.today().year}-{date.today().month:02d}")))


@parq_bp.route("/pagos/<int:pid>/eliminar", methods=["POST"])
@login_required
def eliminar_pago(pid):
    _require("parqueadero.eliminar")
    p = ParqPago.query.get_or_404(pid)
    p.eliminado   = True
    p.eliminado_por = current_user.username
    p.eliminado_en  = datetime.now()
    db.session.commit()
    flash("Pago eliminado.", "success")
    return redirect(request.referrer or url_for("parqueadero.pagos"))


# ── SALIDAS ───────────────────────────────────────────────────────────────────

@parq_bp.route("/salidas")
@login_required
def salidas():
    _require("parqueadero.ver")

    hoy       = date.today()
    mes_param = request.args.get("mes", f"{hoy.year}-{hoy.month:02d}")
    cat_f     = request.args.get("categoria", "")

    query = ParqSalida.query.filter(
        ParqSalida.eliminado == False,
        func.to_char(ParqSalida.fecha, "YYYY-MM") == mes_param,
    )
    if cat_f:
        query = query.filter_by(categoria=cat_f)

    lista = query.order_by(ParqSalida.fecha.desc()).all()
    total = sum(float(s.valor) for s in lista)

    # Totales por categoría
    por_cat = {}
    for s in lista:
        por_cat[s.categoria] = por_cat.get(s.categoria, 0) + float(s.valor)

    return render_template("parqueadero/salidas.html",
        lista=lista, total=total, por_cat=por_cat,
        mes_param=mes_param, cat_f=cat_f, hoy=hoy, cop=_cop,
    )


@parq_bp.route("/salidas/registrar", methods=["POST"])
@login_required
def registrar_salida():
    _require("parqueadero.salidas")

    try:
        valor = float(request.form.get("valor", 0))
        assert valor > 0
    except (ValueError, AssertionError):
        flash("El valor debe ser mayor a cero.", "danger")
        return redirect(url_for("parqueadero.salidas"))

    s = ParqSalida(
        fecha          = date.fromisoformat(request.form.get("fecha")),
        categoria      = request.form.get("categoria"),
        descripcion    = request.form.get("descripcion", "").strip(),
        valor          = valor,
        medio          = request.form.get("medio"),
        registrado_por = current_user.username,
    )
    db.session.add(s)
    db.session.commit()
    flash("Salida registrada.", "success")
    return redirect(url_for("parqueadero.salidas"))


@parq_bp.route("/salidas/<int:sid>/eliminar", methods=["POST"])
@login_required
def eliminar_salida(sid):
    _require("parqueadero.eliminar")
    s = ParqSalida.query.get_or_404(sid)
    s.eliminado    = True
    s.eliminado_por = current_user.username
    s.eliminado_en  = datetime.now()
    db.session.commit()
    flash("Salida eliminada.", "success")
    return redirect(request.referrer or url_for("parqueadero.salidas"))


# ── CIERRE DE CAJA ────────────────────────────────────────────────────────────

@parq_bp.route("/caja/guardar", methods=["POST"])
@login_required
def guardar_cierre():
    _require("parqueadero.pagos")

    hoy = date.today()
    contado = float(request.form.get("efectivo_contado", 0))

    # Calcular efectivo esperado (ingresos en efectivo del día)
    esperado = float(
        db.session.query(func.coalesce(func.sum(ParqPago.valor), 0)).filter(
            ParqPago.eliminado == False,
            ParqPago.fecha_pago == hoy,
            ParqPago.medio == "efectivo",
        ).scalar()
    )

    cierre = ParqCierre.query.filter_by(fecha=hoy).first()
    if cierre:
        cierre.efectivo_esperado = esperado
        cierre.efectivo_contado  = contado
        cierre.diferencia        = contado - esperado
        cierre.observacion       = request.form.get("observacion", "").strip() or None
        cierre.cerrado_por       = current_user.username
    else:
        cierre = ParqCierre(
            fecha             = hoy,
            efectivo_esperado = esperado,
            efectivo_contado  = contado,
            diferencia        = contado - esperado,
            observacion       = request.form.get("observacion", "").strip() or None,
            cerrado_por       = current_user.username,
        )
        db.session.add(cierre)
    db.session.commit()
    flash("Cierre de caja guardado.", "success")
    return redirect(url_for("parqueadero.dashboard"))


# ── ALERTAS ───────────────────────────────────────────────────────────────────

@parq_bp.route("/alertas")
@login_required
def alertas():
    _require("parqueadero.ver")

    hoy = date.today()
    clientes_activos = ParqCliente.query.filter_by(activo=True).all()

    vencidos    = []
    por_vencer  = []
    for c in clientes_activos:
        est = estado_cliente(c, hoy)
        if est["estado"] == "vencido":
            vencidos.append({"cliente": c, "estado": est})
        elif est["estado"] == "por_vencer":
            por_vencer.append({"cliente": c, "estado": est})

    return render_template("parqueadero/alertas.html",
        vencidos=vencidos, por_vencer=por_vencer, hoy=hoy, cop=_cop,
    )


# ── REPORTES ──────────────────────────────────────────────────────────────────

@parq_bp.route("/reportes")
@login_required
def reportes():
    _require("parqueadero.reportes")

    hoy       = date.today()
    mes_param = request.args.get("mes", f"{hoy.year}-{hoy.month:02d}")

    pagos_mes = ParqPago.query.filter(
        ParqPago.eliminado == False,
        func.to_char(ParqPago.fecha_pago, "YYYY-MM") == mes_param,
    ).all()
    salidas_mes = ParqSalida.query.filter(
        ParqSalida.eliminado == False,
        func.to_char(ParqSalida.fecha, "YYYY-MM") == mes_param,
    ).all()

    total_ingresos = sum(float(p.valor) for p in pagos_mes)
    total_salidas  = sum(float(s.valor) for s in salidas_mes)
    utilidad       = total_ingresos - total_salidas

    # Ingresos por concepto
    por_concepto = {}
    for p in pagos_mes:
        por_concepto[p.concepto] = por_concepto.get(p.concepto, 0) + float(p.valor)

    # Ingresos por medio
    por_medio = {
        "efectivo":      sum(float(p.valor) for p in pagos_mes if p.medio == "efectivo"),
        "transferencia": sum(float(p.valor) for p in pagos_mes if p.medio == "transferencia"),
    }

    # Salidas por categoría
    por_cat = {}
    for s in salidas_mes:
        por_cat[s.categoria] = por_cat.get(s.categoria, 0) + float(s.valor)

    # Clientes pendientes del mes
    clientes_activos = ParqCliente.query.filter_by(activo=True).all()
    pendientes = []
    for c in clientes_activos:
        est = estado_cliente(c, hoy)
        if est["estado"] != "al_dia":
            pendientes.append({"cliente": c, "estado": est})

    return render_template("parqueadero/reportes.html",
        mes_param=mes_param, hoy=hoy,
        total_ingresos=total_ingresos, total_salidas=total_salidas, utilidad=utilidad,
        por_concepto=por_concepto, por_medio=por_medio, por_cat=por_cat,
        pendientes=pendientes, pagos_mes=pagos_mes, salidas_mes=salidas_mes,
        cop=_cop,
    )


@parq_bp.route("/reportes/exportar/<tipo>")
@login_required
def exportar(tipo):
    _require("parqueadero.reportes")

    hoy       = date.today()
    mes_param = request.args.get("mes", f"{hoy.year}-{hoy.month:02d}")

    try:
        import io
        from openpyxl import Workbook
        from flask import send_file

        wb = Workbook()
        wb.remove(wb.active)

        if tipo in ("pagos", "todo"):
            ws = wb.create_sheet("Pagos")
            ws.append(["ID", "Cliente", "Placa", "Concepto", "Mes", "Valor",
                        "Fecha", "Medio", "Entidad", "Referencia", "Registrado por"])
            pagos = ParqPago.query.filter(
                ParqPago.eliminado == False,
                func.to_char(ParqPago.fecha_pago, "YYYY-MM") == mes_param,
            ).all()
            for p in pagos:
                ws.append([
                    p.id,
                    p.cliente.nombre if p.cliente else "Ocasional",
                    p.cliente.placa  if p.cliente else "",
                    p.concepto, p.mes_pagado or "", float(p.valor),
                    p.fecha_pago.isoformat(), p.medio, p.entidad or "",
                    p.referencia or "", p.registrado_por or "",
                ])

        if tipo in ("salidas", "todo"):
            ws2 = wb.create_sheet("Salidas")
            ws2.append(["ID", "Fecha", "Categoría", "Descripción", "Valor",
                         "Medio", "Registrado por"])
            salidas = ParqSalida.query.filter(
                ParqSalida.eliminado == False,
                func.to_char(ParqSalida.fecha, "YYYY-MM") == mes_param,
            ).all()
            for s in salidas:
                ws2.append([
                    s.id, s.fecha.isoformat(), s.categoria,
                    s.descripcion, float(s.valor), s.medio, s.registrado_por or "",
                ])

        if tipo in ("clientes", "todo"):
            ws3 = wb.create_sheet("Clientes")
            ws3.append(["ID", "Nombre", "Cédula", "Teléfono", "Placa",
                         "Tipo", "Tarifa", "Día corte", "Desde", "Activo"])
            for c in ParqCliente.query.order_by(ParqCliente.nombre).all():
                ws3.append([
                    c.id, c.nombre, c.cedula or "", c.telefono or "",
                    c.placa, c.tipo_vehiculo, float(c.tarifa_mensual),
                    c.dia_corte, c.fecha_inicio.isoformat(), "Sí" if c.activo else "No",
                ])

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(buf, as_attachment=True,
                         download_name=f"parqueadero_{tipo}_{mes_param}.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except ImportError:
        flash("openpyxl no está instalado. Contacta al administrador.", "danger")
        return redirect(url_for("parqueadero.reportes", mes=mes_param))


# ── API: alertas count (para badge del menú) ──────────────────────────────────

@parq_bp.route("/api/alertas-count")
@login_required
def api_alertas_count():
    if not current_user.tiene_permiso("parqueadero.ver"):
        return jsonify({"count": 0})
    hoy = date.today()
    count = 0
    for c in ParqCliente.query.filter_by(activo=True).all():
        est = estado_cliente(c, hoy)["estado"]
        if est in ("vencido", "por_vencer"):
            count += 1
    return jsonify({"count": count})


# ── CONFIGURACIÓN DE TARIFAS ──────────────────────────────────────────────────

@parq_bp.route("/tarifas", methods=["GET", "POST"])
@login_required
def tarifas():
    _require("parqueadero.clientes")

    if request.method == "POST":
        for tipo in ("carro", "moto"):
            val = request.form.get(f"tarifa_{tipo}")
            if val:
                t = ParqTarifa.query.filter_by(tipo_vehiculo=tipo).first()
                if t:
                    t.valor = float(val)
                    t.actualizado_por = current_user.username
                else:
                    db.session.add(ParqTarifa(
                        tipo_vehiculo=tipo, valor=float(val),
                        actualizado_por=current_user.username,
                    ))
        db.session.commit()
        flash("Tarifas actualizadas.", "success")
        return redirect(url_for("parqueadero.tarifas"))

    lista = ParqTarifa.query.all()
    return render_template("parqueadero/tarifas.html", lista=lista, cop=_cop)

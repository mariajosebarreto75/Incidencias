import os
import uuid
from datetime import date, datetime

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, jsonify, send_from_directory, current_app, abort)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.compromiso import Compromiso, HistorialReprogramacion
from app.models.contrato import Contrato
from app.models.user_contrato import UserContrato
from app.models.reunion import Reunion

compromisos_bp = Blueprint("compromisos", __name__, url_prefix="/compromisos")


def _es_neo():
    """Retorna True si el usuario tiene permisos de escritura completos (neo o admin)."""
    return current_user.rol.lower() in ("neo", "admin")


def _es_gerente():
    return current_user.rol.lower() == "gerente"

ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "pdf"}
UPLOAD_FOLDER_NAME = "evidencias_compromisos"


def _upload_dir():
    base = os.path.join(current_app.root_path, "uploads", UPLOAD_FOLDER_NAME)
    os.makedirs(base, exist_ok=True)
    return base


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def _contratos_usuario():
    """Contratos que el usuario actual puede ver."""
    if current_user.rol in ("admin", "neo", "gerente"):
        return Contrato.query.filter_by(activo=True).order_by(Contrato.contrato).all()
    # coordinador/director: solo sus contratos asignados
    asignados = (UserContrato.query
                 .filter_by(user_id=current_user.id)
                 .with_entities(UserContrato.contrato).all())
    nombres = [a.contrato for a in asignados]
    return (Contrato.query
            .filter(Contrato.contrato.in_(nombres), Contrato.activo == True)
            .order_by(Contrato.contrato).all())


def _puede_ver_contrato(contrato_id):
    contratos = _contratos_usuario()
    return any(c.id == contrato_id for c in contratos)


# ── HUB ──────────────────────────────────────────────────────────────────────

@compromisos_bp.route("/")
@login_required
def index():
    """Hub / página de inicio del módulo compromisos."""
    from datetime import datetime as _dt, timedelta as _td
    now       = _dt.now()
    today     = now.date()
    now_hhmm  = now.strftime("%H:%M")

    # KPIs rápidos para el hub
    contratos = _contratos_usuario()
    ids_contratos = [c.id for c in contratos]

    total_comp   = Compromiso.query.filter(Compromiso.contrato_id.in_(ids_contratos)).count()
    pendientes   = Compromiso.query.filter(Compromiso.contrato_id.in_(ids_contratos),
                                           Compromiso.estado == "Pendiente").count()
    atrasados_q  = [c for c in Compromiso.query.filter(
                       Compromiso.contrato_id.in_(ids_contratos),
                       Compromiso.estado.in_(["Pendiente", "Reprogramado"])).all()
                    if c.atrasado]
    atrasados    = len(atrasados_q)

    # Reuniones hoy: puntuales hoy + recurrentes cuyo weekday coincide con hoy
    today_wd = today.weekday()
    reuniones_hoy_punt = Reunion.query.filter(Reunion.fecha == today,
                                              Reunion.recurrente == False).count()
    reuniones_hoy_rec  = sum(1 for r in Reunion.query.filter(Reunion.recurrente == True).all()
                             if r.fecha.weekday() == today_wd)
    reuniones_hoy = reuniones_hoy_punt + reuniones_hoy_rec

    # Próxima reunión: la que aún no ha comenzado (considerando hora actual)
    candidatos = []  # (fecha, hora_inicio, reunion, fecha_display)

    # 1. Puntuales futuras o de hoy que no han empezado
    for r in (Reunion.query
              .filter(Reunion.recurrente == False, Reunion.fecha >= today)
              .order_by(Reunion.fecha.asc(), Reunion.hora_inicio.asc()).all()):
        if r.fecha > today or r.hora_inicio > now_hhmm:
            candidatos.append((r.fecha, r.hora_inicio, r, r.fecha))

    # 2. Recurrentes: calcular próxima ocurrencia >= hoy
    for r in Reunion.query.filter(Reunion.recurrente == True).all():
        ref_wd  = r.fecha.weekday()
        days_ah = (ref_wd - today_wd) % 7
        if days_ah == 0:
            # Hoy — solo si no empezó aún
            if r.hora_inicio > now_hhmm:
                candidatos.append((today, r.hora_inicio, r, today))
            else:
                next_d = today + _td(days=7)
                candidatos.append((next_d, r.hora_inicio, r, next_d))
        else:
            next_d = today + _td(days=days_ah)
            candidatos.append((next_d, r.hora_inicio, r, next_d))

    candidatos.sort(key=lambda x: (x[0], x[1]))
    proxima        = candidatos[0][2] if candidatos else None
    proxima_fecha  = candidatos[0][3] if candidatos else None

    # Formatear fecha en español para el template
    MESES = ['enero','febrero','marzo','abril','mayo','junio',
             'julio','agosto','septiembre','octubre','noviembre','diciembre']
    DIAS_ES = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
    proxima_fecha_str = ""
    if proxima_fecha:
        proxima_fecha_str = (f"{DIAS_ES[proxima_fecha.weekday()]} "
                             f"{proxima_fecha.day} de {MESES[proxima_fecha.month-1]}")

    if _es_neo():
        tpl = "neo/navbNeo.html"
    elif _es_gerente():
        tpl = "gerente/navb_gerente.html"
    else:
        tpl = "coordinador/navbarcoor.html"

    return render_template(
        "compromisos/hub.html",
        es_neo=_es_neo(),
        base_template=tpl,
        kpi=dict(total=total_comp, pendientes=pendientes, atrasados=atrasados,
                 reuniones_hoy=reuniones_hoy),
        proxima=proxima,
        proxima_fecha_str=proxima_fecha_str,
    )


# ── LISTADO COMPROMISOS ───────────────────────────────────────────────────────

@compromisos_bp.route("/lista/")
@login_required
def lista():
    contratos = _contratos_usuario()
    contrato_id   = request.args.get("contrato_id", type=int)
    atrasado_filtro = request.args.get("atrasado", "")
    q_resp        = request.args.get("q_resp", "").strip()
    fecha_desde   = request.args.get("fecha_desde", "")
    fecha_hasta   = request.args.get("fecha_hasta", "")

    # checkboxes de estado (ausente = todos marcados)
    est_pend = request.args.get("est_pend")
    est_rep  = request.args.get("est_rep")
    est_cerr = request.args.get("est_cerr")
    # si ninguno fue enviado (GET limpio) → todos activos
    estados_sel = []
    if est_pend or est_rep or est_cerr:
        if est_pend: estados_sel.append("Pendiente")
        if est_rep:  estados_sel.append("Reprogramado")
        if est_cerr: estados_sel.append("Cerrado")
    # si se enviaron pero ninguno marcado → igual todos (evita lista vacía)
    if not estados_sel:
        estados_sel = ["Pendiente", "Reprogramado", "Cerrado"]

    q = Compromiso.query.join(Contrato).filter(
        Contrato.id.in_([c.id for c in contratos])
    )

    if contrato_id:
        q = q.filter(Compromiso.contrato_id == contrato_id)

    q = q.filter(Compromiso.estado.in_(estados_sel))

    if q_resp:
        q = q.filter(Compromiso.responsable.ilike(f"%{q_resp}%"))
    if fecha_desde:
        try:
            q = q.filter(Compromiso.fecha_entrega >= date.fromisoformat(fecha_desde))
        except ValueError:
            pass
    if fecha_hasta:
        try:
            q = q.filter(Compromiso.fecha_entrega <= date.fromisoformat(fecha_hasta))
        except ValueError:
            pass

    compromisos = q.order_by(Compromiso.fecha_entrega.asc(), Compromiso.id.desc()).all()

    if atrasado_filtro == "1":
        compromisos = [c for c in compromisos if c.atrasado]
    elif atrasado_filtro == "0":
        compromisos = [c for c in compromisos if not c.atrasado]

    total        = len(compromisos)
    pendientes   = sum(1 for c in compromisos if c.estado == "Pendiente")
    reprogramados = sum(1 for c in compromisos if c.estado == "Reprogramado")
    cerrados     = sum(1 for c in compromisos if c.estado == "Cerrado")
    atrasados_n  = sum(1 for c in compromisos if c.atrasado)

    return render_template(
        "compromisos/index.html",
        compromisos=compromisos,
        contratos=contratos,
        contrato_id_sel=contrato_id,
        atrasado_sel=atrasado_filtro,
        q_resp_sel=q_resp,
        fecha_desde_sel=fecha_desde,
        fecha_hasta_sel=fecha_hasta,
        est_pend_sel=est_pend,
        est_rep_sel=est_rep,
        est_cerr_sel=est_cerr,
        es_neo=_es_neo(),
        base_template="neo/navbNeo.html" if _es_neo() else ("gerente/navb_gerente.html" if _es_gerente() else "coordinador/navbarcoor.html"),
        kpi=dict(total=total, pendientes=pendientes,
                 reprogramados=reprogramados, cerrados=cerrados, atrasados=atrasados_n),
    )


# ── CREAR ─────────────────────────────────────────────────────────────────────

@compromisos_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def nuevo():
    if not _es_neo():
        abort(403)
    contratos = _contratos_usuario()
    if request.method == "POST":
        contrato_id = request.form.get("contrato_id", type=int)
        responsable = request.form.get("responsable", "").strip()
        texto = request.form.get("compromiso", "").strip()
        fecha_entrega_str = request.form.get("fecha_entrega", "")
        obs = request.form.get("observacion_general", "").strip()

        errores = []
        if not contrato_id:
            errores.append("Selecciona un contrato.")
        if not responsable:
            errores.append("El responsable es obligatorio.")
        if not texto:
            errores.append("El texto del compromiso es obligatorio.")
        if not fecha_entrega_str:
            errores.append("La fecha de entrega es obligatoria.")
        else:
            try:
                fecha_entrega = date.fromisoformat(fecha_entrega_str)
            except ValueError:
                errores.append("Fecha inválida.")
                fecha_entrega = None

        if not _puede_ver_contrato(contrato_id):
            errores.append("No tienes acceso a ese contrato.")

        if errores:
            for e in errores:
                flash(e, "danger")
            return render_template("compromisos/form.html", contratos=contratos,
                                   form=request.form)

        comp = Compromiso(
            contrato_id=contrato_id,
            responsable=responsable,
            compromiso=texto,
            fecha_entrega=fecha_entrega,
            observacion_general=obs or None,
        )
        db.session.add(comp)
        db.session.commit()
        flash("Compromiso creado.", "success")
        return redirect(url_for("compromisos.lista"))

    return render_template("compromisos/form.html", contratos=contratos, form={})



# ── REPROGRAMAR ───────────────────────────────────────────────────────────────

@compromisos_bp.route("/<int:comp_id>/reprogramar", methods=["POST"])
@login_required
def reprogramar(comp_id):
    if not _es_neo():
        abort(403)
    comp = Compromiso.query.get_or_404(comp_id)
    if not _puede_ver_contrato(comp.contrato_id):
        abort(403)
    if comp.estado == "Cerrado":
        flash("No se puede reprogramar un compromiso cerrado.", "warning")
        return redirect(url_for("compromisos.lista"))

    nueva_str = request.form.get("nueva_fecha", "")
    try:
        nueva = date.fromisoformat(nueva_str)
    except ValueError:
        flash("Fecha inválida.", "danger")
        return redirect(url_for("compromisos.lista"))

    hist = HistorialReprogramacion(
        compromiso_id=comp.id,
        fecha_anterior=comp.fecha_entrega,
        nueva_fecha=nueva,
    )
    db.session.add(hist)
    comp.fecha_entrega = nueva
    comp.estado = "Reprogramado"
    comp.cantidad_reprogramaciones += 1
    db.session.commit()
    flash("Compromiso reprogramado.", "success")
    return redirect(url_for("compromisos.lista"))


# ── EDITAR ────────────────────────────────────────────────────────────────────

@compromisos_bp.route("/<int:comp_id>/editar", methods=["POST"])
@login_required
def editar(comp_id):
    if not _es_neo():
        abort(403)
    comp = Compromiso.query.get_or_404(comp_id)
    if not _puede_ver_contrato(comp.contrato_id):
        abort(403)

    responsable = request.form.get("responsable", "").strip()
    compromiso  = request.form.get("compromiso", "").strip()
    obs         = request.form.get("observacion_general", "").strip()

    if not responsable or not compromiso:
        flash("Responsable y compromiso son obligatorios.", "danger")
        return redirect(url_for("compromisos.lista"))

    comp.responsable         = responsable
    comp.compromiso          = compromiso
    comp.observacion_general = obs or None
    db.session.commit()
    flash("Compromiso actualizado.", "success")
    return redirect(url_for("compromisos.lista"))


# ── CERRAR ────────────────────────────────────────────────────────────────────

@compromisos_bp.route("/<int:comp_id>/cerrar", methods=["POST"])
@login_required
def cerrar(comp_id):
    if not _es_neo():
        abort(403)
    comp = Compromiso.query.get_or_404(comp_id)
    if not _puede_ver_contrato(comp.contrato_id):
        abort(403)
    if comp.estado == "Cerrado":
        flash("El compromiso ya está cerrado.", "warning")
        return redirect(url_for("compromisos.lista"))

    fecha_real_str = request.form.get("fecha_entrega_real", "")
    obs_cierre = request.form.get("obs_cierre", "").strip()

    try:
        fecha_real = date.fromisoformat(fecha_real_str)
    except ValueError:
        flash("Fecha de cierre inválida.", "danger")
        return redirect(url_for("compromisos.lista"))

    # Evidencia obligatoria para cerrar
    archivo = request.files.get("evidencia")
    tiene_evidencia = bool(comp.evidencia_path)
    if archivo and archivo.filename:
        if _allowed(archivo.filename):
            ext = archivo.filename.rsplit(".", 1)[1].lower()
            nombre_unico = f"{uuid.uuid4().hex}.{ext}"
            archivo.save(os.path.join(_upload_dir(), nombre_unico))
            comp.evidencia_path = nombre_unico
            comp.evidencia_nombre = secure_filename(archivo.filename)
            tiene_evidencia = True

    if not tiene_evidencia:
        flash("Para cerrar el compromiso primero debes subir una evidencia.", "warning")
        return redirect(url_for("compromisos.lista"))

    if obs_cierre:
        sello = datetime.now().strftime("%Y-%m-%d %H:%M")
        actual = comp.observacion_general or ""
        comp.observacion_general = (f"{actual}\n\n[{sello}] {obs_cierre}" if actual
                                    else f"[{sello}] {obs_cierre}")

    comp.fecha_entrega_real = fecha_real
    comp.estado = "Cerrado"
    db.session.commit()
    flash("Compromiso cerrado.", "success")
    return redirect(url_for("compromisos.lista"))


# ── SUBIR EVIDENCIA (standalone) ───────────────────────────────────────────────

@compromisos_bp.route("/<int:comp_id>/evidencia", methods=["POST"])
@login_required
def subir_evidencia(comp_id):
    comp = Compromiso.query.get_or_404(comp_id)
    if not _puede_ver_contrato(comp.contrato_id):
        abort(403)
    archivo = request.files.get("evidencia")
    if not archivo or not archivo.filename:
        flash("No se recibió archivo.", "danger")
        return redirect(url_for("compromisos.lista"))
    if not _allowed(archivo.filename):
        flash("Tipo de archivo no permitido (jpg, png, webp, pdf).", "danger")
        return redirect(url_for("compromisos.lista"))

    # Borrar evidencia anterior si existe
    if comp.evidencia_path:
        old = os.path.join(_upload_dir(), comp.evidencia_path)
        if os.path.exists(old):
            os.remove(old)

    ext = archivo.filename.rsplit(".", 1)[1].lower()
    nombre_unico = f"{uuid.uuid4().hex}.{ext}"
    archivo.save(os.path.join(_upload_dir(), nombre_unico))
    comp.evidencia_path = nombre_unico
    comp.evidencia_nombre = secure_filename(archivo.filename)
    db.session.commit()
    flash("Evidencia guardada.", "success")
    return redirect(url_for("compromisos.lista"))


# ── VER EVIDENCIA ──────────────────────────────────────────────────────────────

@compromisos_bp.route("/<int:comp_id>/evidencia/ver")
@login_required
def ver_evidencia(comp_id):
    comp = Compromiso.query.get_or_404(comp_id)
    if not _puede_ver_contrato(comp.contrato_id):
        abort(403)
    if not comp.evidencia_path:
        abort(404)
    return send_from_directory(_upload_dir(), comp.evidencia_path,
                               download_name=comp.evidencia_nombre or comp.evidencia_path)


# ── ELIMINAR EVIDENCIA ─────────────────────────────────────────────────────────

@compromisos_bp.route("/<int:comp_id>/evidencia/eliminar", methods=["POST"])
@login_required
def eliminar_evidencia(comp_id):
    comp = Compromiso.query.get_or_404(comp_id)
    if not _puede_ver_contrato(comp.contrato_id):
        abort(403)
    if comp.evidencia_path:
        old = os.path.join(_upload_dir(), comp.evidencia_path)
        if os.path.exists(old):
            os.remove(old)
        comp.evidencia_path = None
        comp.evidencia_nombre = None
        db.session.commit()
    flash("Evidencia eliminada.", "success")
    return redirect(url_for("compromisos.lista"))


# ── ELIMINAR COMPROMISO ────────────────────────────────────────────────────────

@compromisos_bp.route("/<int:comp_id>/eliminar", methods=["POST"])
@login_required
def eliminar(comp_id):
    if not _es_neo():
        abort(403)
    comp = Compromiso.query.get_or_404(comp_id)
    if not _puede_ver_contrato(comp.contrato_id):
        abort(403)
    if comp.evidencia_path:
        old = os.path.join(_upload_dir(), comp.evidencia_path)
        if os.path.exists(old):
            os.remove(old)
    db.session.delete(comp)
    db.session.commit()
    flash("Compromiso eliminado.", "success")
    return redirect(url_for("compromisos.lista"))


# ── OBSERVACIÓN (AJAX) ─────────────────────────────────────────────────────────

@compromisos_bp.route("/<int:comp_id>/observacion", methods=["POST"])
@login_required
def guardar_obs(comp_id):
    comp = Compromiso.query.get_or_404(comp_id)
    if not _puede_ver_contrato(comp.contrato_id):
        abort(403)
    texto = request.form.get("texto", "").strip()
    modo = request.form.get("modo", "append")
    if not texto:
        return jsonify(ok=False, error="Texto vacío"), 400

    if modo == "append":
        sello = datetime.now().strftime("%Y-%m-%d %H:%M")
        actual = comp.observacion_general or ""
        comp.observacion_general = (f"{actual}\n\n[{sello}] {texto}" if actual
                                    else f"[{sello}] {texto}")
    else:
        comp.observacion_general = texto
    db.session.commit()
    return jsonify(ok=True, obs=comp.observacion_general)


# ── CREAR CONTRATO RÁPIDO (AJAX) ───────────────────────────────────────────────

@compromisos_bp.route("/contratos/nuevo", methods=["POST"])
@login_required
def crear_contrato_rapido():
    if not _es_neo():
        return jsonify(ok=False, error="Sin permisos"), 403
    nombre = request.form.get("nombre", "").strip()
    if not nombre:
        return jsonify(ok=False, error="El nombre es obligatorio"), 400
    if Contrato.query.filter_by(contrato=nombre).first():
        return jsonify(ok=False, error="Ya existe un contrato con ese nombre"), 409
    c = Contrato(contrato=nombre, activo=True)
    db.session.add(c)
    db.session.commit()
    return jsonify(ok=True, id=c.id, nombre=c.contrato)


# ── ELIMINAR MASIVO ────────────────────────────────────────────────────────────

@compromisos_bp.route("/eliminar-masivo", methods=["POST"])
@login_required
def eliminar_masivo():
    if not _es_neo():
        abort(403)
    ids_raw = request.form.get("ids", "")
    try:
        ids = [int(x) for x in ids_raw.split(",") if x.strip().isdigit()]
    except ValueError:
        flash("IDs inválidos.", "danger")
        return redirect(url_for("compromisos.index"))

    eliminados = 0
    for comp_id in ids:
        comp = Compromiso.query.get(comp_id)
        if comp and _puede_ver_contrato(comp.contrato_id):
            if comp.evidencia_path:
                old = os.path.join(_upload_dir(), comp.evidencia_path)
                if os.path.exists(old):
                    os.remove(old)
            db.session.delete(comp)
            eliminados += 1

    db.session.commit()
    flash(f"{eliminados} compromiso(s) eliminado(s).", "success")
    return redirect(url_for("compromisos.lista"))


# ── EXPORTAR EXCEL ─────────────────────────────────────────────────────────────

@compromisos_bp.route("/exportar-excel")
@login_required
def exportar_excel():
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from flask import Response
        import io
    except ImportError:
        flash("Instala openpyxl para exportar Excel.", "danger")
        return redirect(url_for("compromisos.index"))

    contratos = _contratos_usuario()
    contrato_id = request.args.get("contrato_id", type=int)

    q = Compromiso.query.join(Contrato).filter(
        Contrato.id.in_([c.id for c in contratos])
    )
    if contrato_id:
        q = q.filter(Compromiso.contrato_id == contrato_id)
    compromisos = q.order_by(Compromiso.fecha_entrega.asc()).all()

    # noinspection DuplicatedCode
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Compromisos"

    cabeceras = ["ID", "Contrato", "Responsable", "Compromiso", "Creación",
                 "Entrega", "Estado", "Reprog.", "Cierre real", "Atrasado", "Observación"]
    hdr_fill = PatternFill("solid", fgColor="0D6E6E")
    hdr_font = Font(bold=True, color="FFFFFF")

    ws.append(cabeceras)
    for i, cell in enumerate(ws[1], 1):
        cell.fill = hdr_fill
        cell.font = hdr_font
        cell.alignment = Alignment(horizontal="center")

    for c in compromisos:
        ws.append([
            c.id,
            c.contrato.contrato,
            c.responsable,
            c.compromiso,
            c.fecha_creacion.strftime("%Y-%m-%d"),
            c.fecha_entrega.strftime("%Y-%m-%d"),
            c.estado,
            c.cantidad_reprogramaciones,
            c.fecha_entrega_real.strftime("%Y-%m-%d") if c.fecha_entrega_real else "",
            "Sí" if c.atrasado else "No",
            c.observacion_general or "",
        ])

    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        buf.read(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=compromisos.xlsx"},
    )


# ── IMPORTAR EXCEL ─────────────────────────────────────────────────────────────

@compromisos_bp.route("/importar-excel", methods=["POST"])
@login_required
def importar_excel():
    if not _es_neo():
        abort(403)
    try:
        import pandas as pd
    except ImportError:
        return jsonify({"ok": False, "error": "pandas no disponible"}), 500

    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename.endswith((".xlsx", ".xls")):
        return jsonify({"ok": False, "error": "Archivo inválido. Use .xlsx o .xls"}), 400

    try:
        df = pd.read_excel(archivo)
    except Exception as e:
        return jsonify({"ok": False, "error": f"No se pudo leer el archivo: {e}"}), 400

    # Normalizar nombres de columna
    df.columns = [str(c).strip() for c in df.columns]
    _alias = {
        "fecha creación":         "fecha_creacion",
        "fecha creacion":         "fecha_creacion",
        "contrato":               "contrato",
        "responsable":            "responsable",
        "compromiso":             "compromiso",
        "fecha entrega (acordada)": "fecha_entrega",
        "fecha entrega acordada": "fecha_entrega",
        "fecha entrega":          "fecha_entrega",
        "estado":                 "estado",
        "reprogramaciones":       "cantidad_reprogramaciones",
        "fecha cierre (real)":    "fecha_entrega_real",
        "fecha cierre real":      "fecha_entrega_real",
        "evidencia (url)":        "evidencia_path",
        "evidencia url":          "evidencia_path",
        "atrasado":               "_ignorar",
        "observación general":    "observacion_general",
        "observacion general":    "observacion_general",
    }
    df.rename(columns={c: _alias.get(c.lower(), c.lower()) for c in df.columns}, inplace=True)

    requeridas = {"contrato", "responsable", "compromiso", "fecha_entrega"}
    faltantes = requeridas - set(df.columns)
    if faltantes:
        return jsonify({"ok": False, "error": f"Columnas faltantes: {', '.join(faltantes)}"}), 400

    # Índice de contratos disponibles para el usuario
    contratos_obj = _contratos_usuario()
    contratos_map = {c.contrato.strip().lower(): c for c in contratos_obj}

    insertados = 0
    errores = []

    def _parse_date(val):
        if pd.isna(val) or val == "":
            return None
        if hasattr(val, "date"):
            return val.date()
        try:
            return pd.to_datetime(str(val), dayfirst=True).date()
        except Exception:
            return None

    for i, row in df.iterrows():
        fila = i + 2  # número de fila Excel (1-indexed + cabecera)
        contrato_nombre = str(row.get("contrato", "") or "").strip()
        contrato_obj = contratos_map.get(contrato_nombre.lower())
        if not contrato_obj:
            errores.append(f"Fila {fila}: contrato '{contrato_nombre}' no encontrado")
            continue

        responsable = str(row.get("responsable", "") or "").strip()
        compromiso_txt = str(row.get("compromiso", "") or "").strip()
        if not responsable or not compromiso_txt:
            errores.append(f"Fila {fila}: responsable o compromiso vacío")
            continue

        fecha_entrega = _parse_date(row.get("fecha_entrega"))
        if not fecha_entrega:
            errores.append(f"Fila {fila}: fecha_entrega inválida")
            continue

        fecha_creacion = _parse_date(row.get("fecha_creacion")) or date.today()
        fecha_real     = _parse_date(row.get("fecha_entrega_real"))

        estado = str(row.get("estado", "") or "Pendiente").strip()
        if estado not in ("Pendiente", "En proceso", "Cerrado"):
            estado = "Pendiente"

        try:
            reprog = int(row.get("cantidad_reprogramaciones") or 0)
        except (ValueError, TypeError):
            reprog = 0

        evidencia = str(row.get("evidencia_path", "") or "").strip() or None
        observacion = str(row.get("observacion_general", "") or "").strip() or None

        c = Compromiso(
            contrato_id=contrato_obj.id,
            responsable=responsable,
            compromiso=compromiso_txt,
            fecha_creacion=fecha_creacion,
            fecha_entrega=fecha_entrega,
            fecha_entrega_real=fecha_real,
            estado=estado,
            cantidad_reprogramaciones=reprog,
            evidencia_path=evidencia,
            observacion_general=observacion,
        )
        db.session.add(c)
        insertados += 1

    if insertados:
        db.session.commit()

    return jsonify({
        "ok": True,
        "insertados": insertados,
        "errores": errores,
    })


# ── REUNIONES ─────────────────────────────────────────────────────────────────

@compromisos_bp.route("/reuniones/")
@login_required
def reuniones():
    return render_template(
        "compromisos/reuniones.html",
        es_neo=_es_neo(),
        base_template="neo/navbNeo.html" if _es_neo() else ("gerente/navb_gerente.html" if _es_gerente() else "coordinador/navbarcoor.html"),
        contratos=_contratos_usuario(),
    )


@compromisos_bp.route("/reuniones/semana")
@login_required
def reuniones_semana():
    """Devuelve reuniones en un rango de fechas: ?desde=YYYY-MM-DD&hasta=YYYY-MM-DD"""
    desde_str = request.args.get("desde", "")
    hasta_str = request.args.get("hasta", "")
    try:
        desde = date.fromisoformat(desde_str)
        hasta = date.fromisoformat(hasta_str)
    except ValueError:
        return jsonify(ok=False, error="Fechas inválidas"), 400

    # Reuniones puntuales en el rango
    puntuales = (Reunion.query
                 .filter(Reunion.fecha >= desde, Reunion.fecha <= hasta,
                         Reunion.recurrente == False)
                 .order_by(Reunion.fecha.asc(), Reunion.hora_inicio.asc())
                 .all())

    # Reuniones recurrentes: expandir para cada día del rango que coincida con el weekday
    recurrentes = Reunion.query.filter(Reunion.recurrente == True).all()
    resultado = [r.to_dict() for r in puntuales]
    delta = (hasta - desde).days + 1
    for i in range(delta):
        dia = desde + __import__('datetime').timedelta(days=i)
        for r in recurrentes:
            if r.fecha.weekday() == dia.weekday():
                resultado.append(r.to_dict(fecha_override=dia))

    resultado.sort(key=lambda x: (x["fecha"], x["hora_inicio"]))
    return jsonify(ok=True, reuniones=resultado)


@compromisos_bp.route("/reuniones/nueva", methods=["POST"])
@login_required
def nueva_reunion():
    data = request.get_json(force=True)
    try:
        fecha = date.fromisoformat(data["fecha"])
    except (KeyError, ValueError):
        return jsonify(ok=False, error="Fecha inválida"), 400

    titulo = (data.get("titulo") or "").strip()
    if not titulo:
        return jsonify(ok=False, error="El título es obligatorio"), 400

    hora_inicio = (data.get("hora_inicio") or "").strip()
    hora_fin    = (data.get("hora_fin") or "").strip()
    if not hora_inicio or not hora_fin:
        return jsonify(ok=False, error="Horario obligatorio"), 400

    r = Reunion(
        titulo=titulo,
        descripcion=(data.get("descripcion") or "").strip() or None,
        participantes=(data.get("participantes") or "").strip() or None,
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        contrato_id=data.get("contrato_id") or None,
        recurrente=bool(data.get("recurrente")),
        creado_por=current_user.username if hasattr(current_user, "username") else str(current_user.id),
    )
    db.session.add(r)
    db.session.commit()
    return jsonify(ok=True, reunion=r.to_dict())


@compromisos_bp.route("/reuniones/<int:rid>/editar", methods=["POST"])
@login_required
def editar_reunion(rid):
    r = Reunion.query.get_or_404(rid)
    data = request.get_json(force=True)

    titulo = (data.get("titulo") or "").strip()
    if titulo:
        r.titulo = titulo
    if data.get("descripcion") is not None:
        r.descripcion = (data["descripcion"] or "").strip() or None
    if data.get("participantes") is not None:
        r.participantes = (data["participantes"] or "").strip() or None
    if data.get("hora_inicio"):
        r.hora_inicio = data["hora_inicio"].strip()
    if data.get("hora_fin"):
        r.hora_fin = data["hora_fin"].strip()
    if data.get("fecha"):
        try:
            r.fecha = date.fromisoformat(data["fecha"])
        except ValueError:
            return jsonify(ok=False, error="Fecha inválida"), 400
    if data.get("contrato_id") is not None:
        r.contrato_id = data["contrato_id"] or None
    if "recurrente" in data:
        r.recurrente = bool(data["recurrente"])

    db.session.commit()
    return jsonify(ok=True, reunion=r.to_dict())


@compromisos_bp.route("/reuniones/<int:rid>/eliminar", methods=["POST"])
@login_required
def eliminar_reunion(rid):
    r = Reunion.query.get_or_404(rid)
    db.session.delete(r)
    db.session.commit()
    return jsonify(ok=True)


# ── CHECKLIST ─────────────────────────────────────────────────────────────────

@compromisos_bp.route("/checklist/")
@login_required
def checklist():
    return render_template(
        "compromisos/checklist.html",
        es_neo=_es_neo(),
        base_template="neo/navbNeo.html" if _es_neo() else ("gerente/navb_gerente.html" if _es_gerente() else "coordinador/navbarcoor.html"),
    )

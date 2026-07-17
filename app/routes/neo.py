import os
import uuid

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    send_from_directory,
    current_app,
    abort
)

from flask_login import (
    login_required,
    current_user
)

from datetime import datetime
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.contrato import Contrato
from app.models.distribucion_operativa import DistribucionOperativa
from app.models.meta_operativa import MetaOperativa
from app.models.tipo_desvio import TipoDesvio
from app.models.parametro_neo import ParametroNeo
from app.models.reporte_operacional import ReporteOperacional
from app.models.recurso_contrato import RecursoContrato
from app.models.user_contrato import UserContrato
from app.models.alerta_gps import AlertaGPS
from app.routes.notificaciones import crear_notificacion, coordinadores_de_contrato


neo = Blueprint("neo", __name__)

# Traducción de tipos de alerta GPS → español
TIPOS_ALERTA = {
    "speed_infraction":      "Velocidad excesiva",
    "unscheduled_stop":      "Parada no programada",
    "route_deviation":       "Desvío de ruta",
    "time_deviation":        "Desvío de tiempo",
    "unauthorized_movement": "Movimiento no autorizado",
    "lunch_overtime":        "Almuerzo extendido",
    "execution_overtime":    "OT fuera de tiempo",
    "off_hours_movement":    "Movimiento nocturno",
    "late_departure":        "Salida tardía",
    "early_return":          "Retorno anticipado",
    "long_stop":             "Parada prolongada",
    "entry":                 "Entrada a zona",
    "exit":                  "Salida de zona",
    "both":                  "Entrada y salida",
}


RECURSOS_EXTRA_POR_CONTRATO = {
    "Norte Santander (CW356942) - Perdidas - Cucuta": [
        "CENTRO TECNICO CUCUTA",
        "SEDE CUCUTA",
    ],
    "Santander (CW368183) - Arboricultura - Bucaramanga": [
        "CT BUCARAMANGA",
        "SEDE BUCARAMANGA",
    ],
    "Santander (CW369121) - Arboricultura - Barrancabermeja": [
        "CT BARRANCABERMEJA",
        "SEDE BARRANCABERMEJA",
    ],
    "Tolima (021) - OyMM - Chaparral": [
        "CENTRO TECNICO OYMM CHAPARRAL",
        "SEDE OYMM CHAPARRAL",
    ],
    "Tolima (021) - OyMM - Espinal": [
        "CENTRO TECNICO OYMM ESPINAL",
        "SEDE OYMM ESPINAL",
    ],
    "Tolima Mantenimiento (014) - MTTO - Chaparral": [
        "CENTRO TECNICO MTTO CHAPARRAL",
        "SEDE MTTO CHAPARRAL",
    ],
    "Tolima Mantenimiento (014) - MTTO - Espinal": [
        "CENTRO TECNICO MTTO ESPINAL",
        "SEDE MTTO ESPINAL",
    ],
    "Tolima Mantenimiento (2258) - MTTO - Chaparral": [
        "CENTRO TECNICO MTTO CHAPARRAL",
        "SEDE MTTO CHAPARRAL",
    ],
    "Tolima Mantenimiento (2258) - MTTO - Espinal": [
        "CENTRO TECNICO MTTO ESPINAL",
        "SEDE MTTO ESPINAL",
    ],
    "Valle Norte Integral (2876) - OYMM - Buga": [
        "CENTRO TECNICO BUGA",
        "SEDE BUGA",
    ],
    "Valle Norte Integral (2876) - OYMM - Tulua": [
        "CENTRO TECNICO TULUA",
        "SEDE TULUA",
    ],
    "Valle Norte Integral (2876) - OYMM - Zarzal": [
        "CENTRO TECNICO ZARZAL",
        "SEDE ZARZAL",
    ],
    "Valle Sur Integral (1983) - OYMM - Jamundi": [
        "CENTRO TECNICO JAMUNDI",
        "SEDE JAMUNDI",
    ],
}

# Set plano para verificar rápidamente si un recurso es predefinido
RECURSOS_EXTRA_NEO = {
    r
    for lista in RECURSOS_EXTRA_POR_CONTRATO.values()
    for r in lista
}

EXTENSIONES_PERMITIDAS = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_MB = 10


# ------------------------------------
# Helpers internos
# ------------------------------------

def _extension_ok(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in EXTENSIONES_PERMITIDAS
    )


def _parsear_hora(valor):
    if not valor:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(valor, fmt).time()
        except ValueError:
            continue
    return None


def _parsear_float(valor):
    if not valor:
        return None
    try:
        return float(
            str(valor).replace(".", "").replace(",", ".")
        )
    except (ValueError, TypeError):
        return None


# =====================================
# DISTRIBUCIÓN OPERATIVA (solo lectura)
# =====================================

@neo.route("/neo/distribucion-operativa")
@login_required
def distribucion_neo():
    import json as _json
    from app.models.persona import Persona

    from datetime import date as _date
    hoy = _date.today()

    fecha_desde_str = request.args.get("fecha_desde") or ""
    fecha_hasta_str = request.args.get("fecha_hasta") or ""

    if fecha_desde_str:
        try:
            fecha_desde = datetime.strptime(fecha_desde_str, "%Y-%m-%d").date()
            fecha_hasta = datetime.strptime(fecha_hasta_str or fecha_desde_str, "%Y-%m-%d").date()
        except ValueError:
            fecha_desde = fecha_hasta = hoy
            fecha_desde_str = fecha_hasta_str = str(hoy)
    else:
        # Sin parámetro: usar última fecha con datos en BD
        ultima = DistribucionOperativa.query.order_by(DistribucionOperativa.fecha.desc()).first()
        fecha_desde = fecha_hasta = (ultima.fecha if ultima else hoy)
        fecha_desde_str = fecha_hasta_str = str(fecha_desde)

    # Neo ve TODOS los contratos activos (sin restricción por usuario)
    lista_contratos = sorted(
        c.contrato for c in Contrato.query.filter_by(activo=True).all()
    )

    registros = (
        DistribucionOperativa.query
        .filter(DistribucionOperativa.fecha.between(fecha_desde, fecha_hasta))
        .order_by(DistribucionOperativa.fecha.asc(), DistribucionOperativa.id.asc())
        .all()
    )

    cedulas = {r.cedula_1 for r in registros if r.cedula_1}
    personas_map = {
        p.Documento: p.Nombre
        for p in Persona.query.filter(Persona.Documento.in_(cedulas)).all()
    } if cedulas else {}

    datos_tabla = []
    for r in registros:
        datos_tabla.append({
            "fecha":            str(r.fecha),
            "contrato":         r.contrato or "",
            "recurso":          r.recurso or "",
            "placa":            r.placa or "",
            "orden_trabajo":    r.orden_trabajo or "",
            "tipo_actividad":   r.tipo_actividad or "",
            "tipo_cuadrilla":   r.tipo_cuadrilla or "",
            "meta":             r.meta,
            "cedula_1":         r.cedula_1 or "",
            "nombre_1":         personas_map.get(r.cedula_1, ""),
            "cedula_2":         r.cedula_2 or "",
            "cedula_3":         r.cedula_3 or "",
            "cedula_4":         r.cedula_4 or "",
            "cedula_5":         r.cedula_5 or "",
            "latitud":          r.latitud or "",
            "longitud":         r.longitud or "",
            "duracion_actividad": r.duracion_actividad or "",
            "observacion":      r.observacion or "",
            "origen":           r.origen or "manual",
        })

    return render_template(
        "neo/distribucion_neo.html",
        datos_tabla=_json.dumps(datos_tabla, ensure_ascii=False),
        lista_contratos=lista_contratos,
        fecha_desde=fecha_desde_str,
        fecha_hasta=fecha_hasta_str,
    )


# =====================================
# HOME NEO
# =====================================

@neo.route("/neo")
@login_required
def home_neo():

    nombre = current_user.nombre_completo.title()

    return render_template(
        "neo/home.html",
        nombre = nombre
    )


# =====================================
# VALIDAR REPORTES
# =====================================

@neo.route("/neo/validar-reportes")
@login_required
def validar_reportes():
    from datetime import date as _date

    # Filtrar por contratos asignados al usuario; si no tiene asignados, solo los suyos
    asignados = UserContrato.query.filter_by(user_id=current_user.id).all()
    if asignados:
        contratos_visibles = [uc.contrato for uc in asignados]
        q = ReporteOperacional.query.filter(
            ReporteOperacional.contrato.in_(contratos_visibles)
        )
    else:
        q = ReporteOperacional.query.filter_by(reportado_por=current_user.username)

    fecha_ini     = request.args.get("fecha_ini", "").strip()
    fecha_fin     = request.args.get("fecha_fin", "").strip()
    fecha_rep_ini = request.args.get("fecha_rep_ini", "").strip()
    fecha_rep_fin = request.args.get("fecha_rep_fin", "").strip()
    recurso_f     = request.args.get("recurso", "").strip()
    contrato_f    = request.args.get("contrato", "").strip()

    if fecha_ini:
        try:
            q = q.filter(ReporteOperacional.fecha_creado >=
                         datetime.strptime(fecha_ini, "%Y-%m-%d"))
        except ValueError:
            pass
    if fecha_fin:
        try:
            q = q.filter(ReporteOperacional.fecha_creado <=
                         datetime.strptime(fecha_fin, "%Y-%m-%d").replace(
                             hour=23, minute=59, second=59))
        except ValueError:
            pass
    if fecha_rep_ini:
        try:
            q = q.filter(ReporteOperacional.fecha_reporte >=
                         datetime.strptime(fecha_rep_ini, "%Y-%m-%d").date())
        except ValueError:
            pass
    if fecha_rep_fin:
        try:
            q = q.filter(ReporteOperacional.fecha_reporte <=
                         datetime.strptime(fecha_rep_fin, "%Y-%m-%d").date())
        except ValueError:
            pass
    if recurso_f:
        q = q.filter(ReporteOperacional.recurso.ilike(f"%{recurso_f}%"))
    if contrato_f:
        q = q.filter(ReporteOperacional.contrato == contrato_f)

    reportes = q.order_by(ReporteOperacional.fecha_creado.desc()).all()

    # Listas para los selectores de filtro (todos mis reportes, sin filtrar)
    todos = (
        ReporteOperacional.query
        .filter_by(reportado_por=current_user.username)
        .with_entities(ReporteOperacional.contrato, ReporteOperacional.recurso)
        .distinct()
        .all()
    )
    lista_contratos = sorted({r.contrato for r in todos if r.contrato})
    lista_recursos  = sorted({r.recurso  for r in todos if r.recurso})

    filtros = {
        "fecha_ini":     fecha_ini,
        "fecha_fin":     fecha_fin,
        "fecha_rep_ini": fecha_rep_ini,
        "fecha_rep_fin": fecha_rep_fin,
        "recurso":       recurso_f,
        "contrato":      contrato_f,
    }

    return render_template(
        "neo/validar_reportes.html",
        reportes=reportes,
        lista_contratos=lista_contratos,
        lista_recursos=lista_recursos,
        filtros=filtros,
    )


# =====================================
# ELIMINAR REPORTES (NEO)
# =====================================

@neo.route("/neo/eliminar-reportes", methods=["POST"])
@login_required
def eliminar_reportes():
    d   = request.get_json(silent=True) or {}
    ids = [int(i) for i in (d.get("ids") or []) if str(i).isdigit()]

    if not ids:
        return jsonify({"ok": False, "error": "No se seleccionaron reportes"}), 400

    eliminados = 0
    for rid in ids:
        reporte = ReporteOperacional.query.get(rid)
        if not reporte:
            continue
        # Eliminar archivos físicos de evidencias NEO
        for campo in ("evidencia_1", "evidencia_2"):
            ruta = getattr(reporte, campo, None)
            if ruta:
                ruta_abs = os.path.join(current_app.root_path, ruta)
                if os.path.isfile(ruta_abs):
                    try:
                        os.remove(ruta_abs)
                    except OSError:
                        pass
        db.session.delete(reporte)
        eliminados += 1

    db.session.commit()
    return jsonify({"ok": True, "eliminados": eliminados})


# =====================================
# DETALLE REPORTE (lectura NEO)
# =====================================

@neo.route("/neo/reporte/<int:id>")
@login_required
def detalle_neo(id):
    reporte = ReporteOperacional.query.get_or_404(id)
    if current_user.rol.lower() == "neo":
        asignados = UserContrato.query.filter_by(user_id=current_user.id).all()
        if asignados:
            contratos_visibles = [uc.contrato for uc in asignados]
            if reporte.contrato not in contratos_visibles:
                abort(403)
        elif reporte.reportado_por != current_user.username:
            abort(403)
    return render_template("neo/detalle_neo.html", reporte=reporte)


# =====================================
# VALIDAR CONFORMIDAD (NEO responde)
# =====================================

@neo.route("/neo/reporte/<int:id>/validar", methods=["POST"])
@login_required
def validar_reporte(id):
    reporte = ReporteOperacional.query.get_or_404(id)
    if reporte.reportado_por != current_user.username:
        abort(403)
    if reporte.estado != "Respondido":
        return jsonify({"ok": False, "error": "El coordinador aún no ha respondido"}), 400

    datos = request.get_json()
    conformidad = (datos.get("conformidad_neo") or "").strip()
    obs = (datos.get("observacion_conformidad") or "").strip()

    if conformidad not in ("Conforme", "No conforme"):
        return jsonify({"ok": False, "error": "Seleccione un valor de conformidad"}), 400

    reporte.conformidad_neo = conformidad
    reporte.observacion_conformidad = obs or None
    db.session.commit()

    # Notificar al coordinador solo si es No conforme
    if conformidad == "No conforme":
        for coor in coordinadores_de_contrato(reporte.contrato):
            crear_notificacion(coor, "no_conforme", reporte)
        db.session.commit()

    return jsonify({"ok": True})


# =====================================
# EDITAR REPORTE (NEO)
# =====================================

@neo.route("/neo/reporte/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_reporte(id):
    from datetime import timedelta, date as _date

    reporte = ReporteOperacional.query.get_or_404(id)
    if reporte.reportado_por != current_user.username:
        abort(403)

    if request.method == "POST":
        d = request.get_json(silent=True) or {}

        # Fecha reporte
        try:
            reporte.fecha_reporte = datetime.strptime(d["fecha_reporte"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            pass

        # Horas → recalcular duracion y horas_afectadas
        hi = _parsear_hora(d.get("hora_inicio"))
        hf = _parsear_hora(d.get("hora_fin"))
        if hi:
            reporte.hora_inicio = hi
        if hf:
            reporte.hora_fin = hf

        diff_min = 0
        if reporte.hora_inicio and reporte.hora_fin:
            dt_ini = datetime.combine(_date.today(), reporte.hora_inicio)
            dt_fin = datetime.combine(_date.today(), reporte.hora_fin)
            if dt_fin <= dt_ini:
                dt_fin += timedelta(days=1)
            diff_min = int((dt_fin - dt_ini).total_seconds() // 60)
            h, m = divmod(diff_min, 60)
            reporte.duracion = f"{h}h {m:02d}m"
            reporte.horas_afectadas = round(diff_min / 60, 6)

        # Campos texto
        for campo in ("placa", "tipo_actividad", "tipo_cuadrilla",
                      "tipo_incidencia", "parametro_neo", "observacion"):
            if campo in d:
                setattr(reporte, campo, d[campo] or None)

        # Recalcular impacto
        tipo_lower = (reporte.tipo_incidencia or "").lower()
        impactos_altos = {
            "fuera de ruta", "tiempo muerto", "inicio tardío de labores",
            "salida tardia", "finalización temprana",
            "error en la información", "mal enrutamiento"
        }
        if tipo_lower in impactos_altos:
            reporte.impacto = "Alto"
        elif "excede tiempo" in tipo_lower:
            if diff_min < 15:
                reporte.impacto = "Bajo"
            elif diff_min < 25:
                reporte.impacto = "Medio"
            else:
                reporte.impacto = "Alto"

        # Recalcular afectación económica
        if reporte.impacto and reporte.horas_afectadas:
            tarifas = {"Bajo": 20000, "Medio": 50000, "Alto": 100000}
            reporte.afectacion_economica = (
                tarifas.get(reporte.impacto, 0) * reporte.horas_afectadas
            )

        # Evidencias (solo si se subió algo nuevo)
        if d.get("evidencia_1"):
            reporte.evidencia_1 = d["evidencia_1"]
        if "evidencia_2" in d:
            reporte.evidencia_2 = d["evidencia_2"] or None

        db.session.commit()
        return jsonify({"ok": True})

    # GET
    tipos_desvio  = TipoDesvio.query.order_by(TipoDesvio.tipo_desvio).all()
    parametros_neo = ParametroNeo.query.order_by(ParametroNeo.parametroNeo).all()
    return render_template(
        "neo/editar_reporte.html",
        reporte=reporte,
        tipos_desvio=tipos_desvio,
        parametros_neo=parametros_neo
    )


# =====================================
# PANEL REPORTES NEO
# =====================================

@neo.route("/neo/panelReportes")
@login_required
def panel_reportes():

    tipos_desvio   = TipoDesvio.query.order_by(TipoDesvio.tipo_desvio).all()
    parametros_neo = ParametroNeo.query.order_by(ParametroNeo.parametroNeo).all()

    # Datos de alerta GPS pre-cargados (cuando se llega desde "Resolver")
    alerta_ctx = None
    alerta_id  = request.args.get("alerta_id", "").strip()
    if alerta_id:
        alerta_obj = AlertaGPS.query.get(alerta_id)
        if alerta_obj and alerta_obj.estado_local == "pendiente":
            # Resolver nombre completo del contrato desde código corto
            contrato_nombre = alerta_obj.contract_code or ""
            if alerta_obj.contract_code:
                c_obj = Contrato.query.filter_by(codigo=alerta_obj.contract_code).first()
                if c_obj:
                    contrato_nombre = c_obj.contrato
            alerta_ctx = {
                "id":             alerta_obj.id,
                "placa":          alerta_obj.vehicle_plate or "",
                "contrato":       contrato_nombre,
                "recurso":        alerta_obj.resource_code or "",
                "orden_trabajo":  alerta_obj.order_number  or "",
                "tipo_cuadrilla": alerta_obj.brigade_type  or "",
            }

    return render_template(
        "neo/panelReportes.html",
        tipos_desvio   = tipos_desvio,
        parametros_neo = parametros_neo,
        alerta_ctx     = alerta_ctx,
    )


# =====================================
# API: CONTRATOS POR FECHA (distribución)
# =====================================

@neo.route("/neo/contratos-distribucion")
@login_required
def contratos_distribucion():
    fecha_str = request.args.get("fecha", "").strip()
    if not fecha_str:
        return jsonify([])
    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify([])

    filas = (
        db.session.query(DistribucionOperativa.contrato)
        .filter(
            DistribucionOperativa.fecha    == fecha,
            DistribucionOperativa.contrato != None,
            DistribucionOperativa.contrato != ""
        )
        .distinct()
        .order_by(DistribucionOperativa.contrato)
        .all()
    )
    return jsonify([r[0] for r in filas if r[0]])


# =====================================
# API: RECURSOS POR FECHA + CONTRATO
# =====================================

@neo.route("/neo/recursos")
@login_required
def obtener_recursos():

    fecha_str = request.args.get("fecha",    "").strip()
    contrato  = request.args.get("contrato", "").strip()

    if not fecha_str or not contrato:
        return jsonify([])

    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify([])

    filas = (
        db.session.query(DistribucionOperativa.recurso)
        .filter(
            DistribucionOperativa.fecha    == fecha,
            DistribucionOperativa.contrato == contrato,
            DistribucionOperativa.recurso  != None,
            DistribucionOperativa.recurso  != ""
        )
        .distinct()
        .order_by(DistribucionOperativa.recurso)
        .all()
    )

    recursos_op = sorted(r[0] for r in filas if r[0])

    filas_rc = (
        RecursoContrato.query
        .filter_by(contrato=contrato)
        .filter(
            db.or_(
                RecursoContrato.recurso.ilike("Centro Tecnico%"),
                RecursoContrato.recurso.ilike("Centro Técnico%"),
                RecursoContrato.recurso.ilike("CT %"),
                RecursoContrato.recurso.ilike("SEDE %"),
            )
        )
        .all()
    )
    recursos_extra = [rc.recurso for rc in filas_rc if rc.recurso not in set(recursos_op)]

    return jsonify(recursos_op + recursos_extra)


# =====================================
# API: DATOS OPERATIVOS
# =====================================

@neo.route("/neo/datos-operativos")
@login_required
def datos_operativos():

    fecha_str = request.args.get("fecha",    "").strip()
    contrato  = request.args.get("contrato", "").strip()
    recurso   = request.args.get("recurso",  "").strip()

    if not fecha_str or not contrato or not recurso:
        return jsonify({"success": False})

    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"success": False})

    registros = DistribucionOperativa.query.filter_by(
        fecha=fecha, contrato=contrato, recurso=recurso
    ).all()

    if not registros:
        ru = recurso.upper()
        es_predefinido = (
            ru.startswith("CENTRO TECNICO")
            or ru.startswith("CENTRO TÉCNICO")
            or ru.startswith("CT ")
            or ru.startswith("SEDE ")
        )
        if es_predefinido:
            return jsonify({"success": True, "extra": True, "ordenes": []})
        return jsonify({"success": False})

    ordenes = []
    for r in registros:
        meta_valor = ""
        if r.tipo_cuadrilla:
            meta_obj = MetaOperativa.query.filter_by(
                contrato=contrato,
                Tipo_cuadrilla=r.tipo_cuadrilla
            ).first()
            if meta_obj:
                meta_valor = "{:,.0f}".format(
                    meta_obj.Meta_Produccion
                ).replace(",", ".")
        ordenes.append({
            "orden_trabajo":  r.orden_trabajo  or "",
            "tipo_actividad": r.tipo_actividad or "",
            "tipo_cuadrilla": r.tipo_cuadrilla or "",
            "placa":          r.placa          or "",
            "meta":           meta_valor
        })

    return jsonify({"success": True, "ordenes": ordenes})


# =====================================
# SUBIR EVIDENCIA
# =====================================

@neo.route("/neo/subir-evidencia", methods=["POST"])
@login_required
def subir_evidencia():

    archivo = request.files.get("archivo")

    if not archivo or not archivo.filename:
        return jsonify({
            "success": False,
            "mensaje": "No se recibió ningún archivo."
        }), 400

    if not _extension_ok(archivo.filename):
        return jsonify({
            "success": False,
            "mensaje": "Tipo de archivo no permitido. Use JPG, PNG o WEBP."
        }), 400

    # Validar tamaño
    archivo.seek(0, 2)
    size_mb = archivo.tell() / (1024 * 1024)
    archivo.seek(0)

    if size_mb > MAX_MB:
        return jsonify({
            "success": False,
            "mensaje": f"El archivo supera {MAX_MB} MB."
        }), 400

    # Construir ruta organizada por fecha
    ahora     = datetime.now()
    anio      = str(ahora.year)
    mes       = str(ahora.month).zfill(2)
    ext       = secure_filename(archivo.filename).rsplit(".", 1)[1].lower()
    nombre    = f"{ahora.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.{ext}"

    directorio_abs = os.path.join(
        current_app.root_path, "uploads", "evidencias", anio, mes
    )
    os.makedirs(directorio_abs, exist_ok=True)

    ruta_relativa = f"uploads/evidencias/{anio}/{mes}/{nombre}"
    archivo.save(os.path.join(directorio_abs, nombre))

    return jsonify({
        "success": True,
        "ruta":    ruta_relativa,
        "url":     f"/neo/evidencia/{ruta_relativa}"
    })


# =====================================
# VER IMAGEN
# =====================================

@neo.route("/neo/evidencia/<path:ruta>")
@login_required
def ver_evidencia(ruta):

    ruta_abs   = os.path.join(current_app.root_path, ruta)
    directorio = os.path.dirname(ruta_abs)
    nombre     = os.path.basename(ruta_abs)

    return send_from_directory(directorio, nombre)


# =====================================
# DESCARGAR IMAGEN
# =====================================

@neo.route("/neo/descargar/<path:ruta>")
@login_required
def descargar_evidencia(ruta):

    ruta_abs   = os.path.join(current_app.root_path, ruta)
    directorio = os.path.dirname(ruta_abs)
    nombre     = os.path.basename(ruta_abs)

    return send_from_directory(directorio, nombre, as_attachment=True)


# =====================================
# GUARDAR REPORTE
# =====================================

@neo.route("/neo/guardar-reporte", methods=["POST"])
@login_required
def guardar_reporte():

    datos = request.get_json()

    # Validar obligatorios
    requeridos = {
        "fecha_reporte":     "Fecha del Reporte",
        "contrato":          "Contrato",
        "recurso":           "Recurso",
        "hora_inicio":       "Hora Inicio",
        "hora_fin":          "Hora Fin",
        "tipo_incidencia":   "Tipo de Incidencia",
        "observacion":       "Observación",
        "evidencia_1":       "Evidencia 1",
    }

    faltantes = [
        label for campo, label in requeridos.items()
        if not datos.get(campo)
    ]

    if faltantes:
        return jsonify({
            "success": False,
            "mensaje": "Campos requeridos: " + ", ".join(faltantes)
        }), 400

    try:
        fecha       = datetime.strptime(datos["fecha_reporte"], "%Y-%m-%d").date()
        hora_inicio = _parsear_hora(datos["hora_inicio"])
        hora_fin    = _parsear_hora(datos["hora_fin"])
    except (ValueError, TypeError) as e:
        return jsonify({
            "success": False,
            "mensaje": f"Formato de fecha u hora inválido: {e}"
        }), 400

    try:
        reporte = ReporteOperacional(
            fecha_reporte       = fecha,
            contrato            = datos["contrato"],
            recurso             = datos["recurso"],
            placa               = datos.get("placa")           or None,
            orden_trabajo       = datos.get("orden_trabajo")   or None,
            tipo_actividad      = datos.get("tipo_actividad")  or None,
            tipo_cuadrilla      = datos.get("tipo_cuadrilla")  or None,
            meta                = _parsear_float(datos.get("meta")),
            hora_inicio         = hora_inicio,
            hora_fin            = hora_fin,
            # Guardamos el texto histórico, no el ID del catálogo
            tipo_incidencia     = datos.get("tipo_incidencia_nombre") or datos["tipo_incidencia"],
            parametro_neo       = datos.get("parametro_neo_nombre")   or "",
            observacion         = datos.get("observacion")            or "",
            duracion            = datos.get("duracion")               or None,
            impacto             = datos.get("impacto")                or None,
            horas_afectadas     = _parsear_float(datos.get("horas_afectadas")),
            afectacion_economica = _parsear_float(datos.get("afectacion")),
            evidencia_1         = datos["evidencia_1"],
            evidencia_2         = datos.get("evidencia_2") or None,
            reportado_por       = current_user.username,
            estado              = "Abierto"
        )

        db.session.add(reporte)
        db.session.commit()

        # Notificar a coordinadores del contrato
        for coor in coordinadores_de_contrato(reporte.contrato):
            crear_notificacion(coor, "nuevo_reporte", reporte)
        db.session.commit()

        recurso_val  = datos["recurso"]
        contrato_val = datos["contrato"]
        rv = recurso_val.upper()
        es_predefinido = (
            rv.startswith("CENTRO TECNICO")
            or rv.startswith("CENTRO TÉCNICO")
            or rv.startswith("CT ")
            or rv.startswith("SEDE ")
        )
        if es_predefinido:
            existe_rc = RecursoContrato.query.filter_by(
                recurso=recurso_val, contrato=contrato_val
            ).first()
            if not existe_rc:
                db.session.add(RecursoContrato(
                    recurso=recurso_val,
                    contrato=contrato_val
                ))
                db.session.commit()

        # Si el reporte viene de una alerta GPS, resolverla ahora
        alerta_id_from = datos.get("alerta_id")
        if alerta_id_from:
            alerta_obj = AlertaGPS.query.get(int(alerta_id_from))
            if alerta_obj and alerta_obj.estado_local == "pendiente":
                try:
                    from app.services.gps_monitor import responder_alertas
                    responder_alertas([{"alert_id": alerta_obj.alert_id_gps, "accion": "resolver"}])
                except Exception:
                    pass  # No bloquear si GPS Monitor falla
                alerta_obj.estado_local   = "resuelta"
                alerta_obj.atendida_por   = current_user.username
                alerta_obj.fecha_atencion = datetime.utcnow()
                db.session.commit()

        return jsonify({
            "success":   True,
            "id":        reporte.id,
            "mensaje":   f"Reporte #{reporte.id} guardado correctamente.",
            "alerta_id": alerta_id_from,
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "mensaje": str(e)
        }), 500


# =============================================
# ALERTAS GPS
# =============================================

def _codigos_contrato_usuario():
    """Devuelve los códigos de contrato (código corto) del usuario actual."""
    uc = UserContrato.query.filter_by(user_id=current_user.id).all()
    if not uc:
        return []
    contratos_obj = Contrato.query.filter(
        Contrato.contrato.in_([u.contrato for u in uc])
    ).all()
    return [c.codigo for c in contratos_obj if c.codigo]


@neo.route("/neo/alertas")
@login_required
def alertas_gps():
    codigos_contrato = _codigos_contrato_usuario()

    filtro   = request.args.get("filtro",   "pendiente")
    placa    = request.args.get("placa",    "").strip().upper()
    contrato = request.args.get("contrato", "").strip()
    recurso  = request.args.get("recurso",  "").strip()
    orden    = request.args.get("orden",    "reciente")
    fecha    = request.args.get("fecha",    "").strip()   # YYYY-MM-DD, vacío = todas
    # "todos" | "con_contrato" | "sin_contrato"
    scope    = request.args.get("scope",    "todos")

    q = AlertaGPS.query
    # Filtro de estado (pendiente / resuelta / todas)
    if filtro != "todas":
        q = q.filter(AlertaGPS.estado_local == filtro)
    # Filtro de scope
    if scope == "sin_contrato":
        q = q.filter(AlertaGPS.contract_code == None)
    elif scope == "con_contrato":
        q = q.filter(AlertaGPS.contract_code != None)
    # Filtro de fecha
    if fecha:
        try:
            from datetime import datetime as _dt
            f_date = _dt.strptime(fecha, "%Y-%m-%d").date()
            q = q.filter(db.func.date(AlertaGPS.triggered_at) == f_date)
        except ValueError:
            pass
    # Filtros adicionales
    if placa:
        q = q.filter(AlertaGPS.vehicle_plate.ilike(f"%{placa}%"))
    if contrato:
        q = q.filter(AlertaGPS.contract_code == contrato)
    if recurso:
        q = q.filter(AlertaGPS.resource_code.ilike(f"%{recurso}%"))

    if orden == "antiguo":
        q = q.order_by(AlertaGPS.triggered_at.asc())
    else:
        q = q.order_by(AlertaGPS.triggered_at.desc())

    alertas = q.all()

    # Agrupar: tipo_es → placa → lista de alertas (desc por fecha)
    # Mostramos la más reciente de cada placa con el conteo total
    import json as _json
    grupos = {}
    for a in alertas:
        tipo_es = TIPOS_ALERTA.get(a.alert_type, a.alert_type or "Otro")
        plate   = a.vehicle_plate or "—"
        if tipo_es not in grupos:
            grupos[tipo_es] = {}
        if plate not in grupos[tipo_es]:
            grupos[tipo_es][plate] = []
        grupos[tipo_es][plate].append(a)

    # Parsear metadata_raw para cada alerta (speed, tiempo, distancia)
    extras = {}  # alert.id → dict con campos extras para mostrar
    for a in alertas:
        ex = {}
        if a.metadata_raw:
            try:
                raw = a.metadata_raw
                # puede venir como string doble-encoded
                m = _json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(m, str):
                    m = _json.loads(m)
                if isinstance(m, dict):
                    if "max_speed_kmh" in m:
                        ex["velocidad"] = m["max_speed_kmh"]
                    if "duration_sec" in m:
                        mins = round(m["duration_sec"] / 60, 1)
                        ex["duracion_min"] = mins
                    if "point_count" in m:
                        ex["puntos"] = m["point_count"]
            except Exception:
                pass
        extras[a.id] = ex

    total_pendientes = AlertaGPS.query.filter_by(estado_local="pendiente").count()

    # Lista de contratos disponibles para el selector (todos los distintos en BD)
    from sqlalchemy import distinct
    todos_contratos = [
        r[0] for r in
        AlertaGPS.query.with_entities(distinct(AlertaGPS.contract_code))
                       .filter(AlertaGPS.contract_code != None)
                       .order_by(AlertaGPS.contract_code).all()
    ]

    return render_template(
        "neo/alertas_gps.html",
        grupos           = grupos,
        extras           = extras,
        filtro           = filtro,
        placa            = placa,
        contrato         = contrato,
        recurso          = recurso,
        orden            = orden,
        scope            = scope,
        codigos_contrato = todos_contratos,
        total_alertas    = len(alertas),
        total_pendientes = total_pendientes,
    )


@neo.route("/neo/alertas/<int:id>/responder", methods=["POST"])
@login_required
def responder_alerta_gps(id):
    alerta = AlertaGPS.query.get_or_404(id)
    datos  = request.get_json() or {}
    accion = datos.get("accion")

    if accion not in ("resolver", "liberar"):
        return jsonify({"ok": False, "error": "Accion invalida"}), 400

    try:
        from app.services.gps_monitor import responder_alertas
        resultado = responder_alertas([{"alert_id": alerta.alert_id_gps, "accion": accion}])
        if resultado and resultado[0]["ok"]:
            alerta.estado_local   = "resuelta" if accion == "resolver" else "liberada"
            alerta.atendida_por   = current_user.username
            alerta.fecha_atencion = datetime.utcnow()
            db.session.commit()
            return jsonify({"ok": True})
        else:
            detalle = resultado[0]["detalle"] if resultado else "Sin respuesta"
            return jsonify({"ok": False, "error": detalle})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@neo.route("/neo/alertas/badge")
@login_required
def badge_alertas():
    count = AlertaGPS.query.filter_by(estado_local="pendiente").count()
    return jsonify({"pendientes": count})


@neo.route("/neo/alertas/datos")
@login_required
def alertas_datos():
    """Devuelve las alertas como JSON para el drawer del panel de reportes."""
    import json as _json

    filtro   = request.args.get("filtro",   "pendiente")
    placa    = request.args.get("placa",    "").strip().upper()
    contrato = request.args.get("contrato", "").strip()
    recurso  = request.args.get("recurso",  "").strip()
    orden    = request.args.get("orden",    "reciente")
    scope    = request.args.get("scope",    "todos")

    q = AlertaGPS.query
    if filtro != "todas":
        q = q.filter(AlertaGPS.estado_local == filtro)
    if scope == "sin_contrato":
        q = q.filter(AlertaGPS.contract_code == None)
    elif scope == "con_contrato":
        q = q.filter(AlertaGPS.contract_code != None)
    if placa:
        q = q.filter(AlertaGPS.vehicle_plate.ilike(f"%{placa}%"))
    if contrato:
        q = q.filter(AlertaGPS.contract_code == contrato)
    if recurso:
        q = q.filter(AlertaGPS.resource_code.ilike(f"%{recurso}%"))

    if orden == "antiguo":
        q = q.order_by(AlertaGPS.triggered_at.asc())
    else:
        q = q.order_by(AlertaGPS.triggered_at.desc())

    alertas = q.all()

    # Agrupar tipo_es → placa → alertas
    grupos = {}
    for a in alertas:
        tipo_es = TIPOS_ALERTA.get(a.alert_type, a.alert_type or "Otro")
        plate   = a.vehicle_plate or "—"
        grupos.setdefault(tipo_es, {}).setdefault(plate, []).append(a)

    resultado = []
    for tipo, por_placa in grupos.items():
        grupo_total = sum(len(v) for v in por_placa.values())
        items = []
        for plate, lst in por_placa.items():
            a   = lst[0]
            cnt = len(lst)
            ex  = {}
            if a.metadata_raw:
                try:
                    m = _json.loads(a.metadata_raw)
                    if isinstance(m, str):
                        m = _json.loads(m)
                    if isinstance(m, dict):
                        if "max_speed_kmh" in m:
                            ex["velocidad"] = m["max_speed_kmh"]
                        if "duration_sec" in m:
                            ex["duracion_min"] = round(m["duration_sec"] / 60, 1)
                except Exception:
                    pass
            items.append({
                "id":           a.id,
                "plate":        a.vehicle_plate or "—",
                "triggered_at": a.triggered_at or "",
                "contract":     a.contract_code or "",
                "resource":     a.resource_code or "",
                "brigade":      a.brigade_type or "",
                "plan_date":    a.plan_date or "",
                "order":        a.order_number or "",
                "lat":          a.lat,
                "lon":          a.lon,
                "estado":       a.estado_local,
                "atendida_por": a.atendida_por or "",
                "tech1":        str(a.tech1_doc) if a.tech1_doc else "",
                "tech2":        str(a.tech2_doc) if a.tech2_doc else "",
                "tech3":        str(a.tech3_doc) if a.tech3_doc else "",
                "tech4":        str(a.tech4_doc) if a.tech4_doc else "",
                "tech5":        str(a.tech5_doc) if a.tech5_doc else "",
                "count":        cnt,
                "velocidad":    ex.get("velocidad", ""),
                "duracion_min": ex.get("duracion_min", ""),
            })
        resultado.append({"tipo": tipo, "total": grupo_total, "items": items})

    pendientes = AlertaGPS.query.filter_by(estado_local="pendiente").count()

    from sqlalchemy import distinct as _distinct
    todos_contratos = [
        r[0] for r in
        AlertaGPS.query.with_entities(_distinct(AlertaGPS.contract_code))
                       .filter(AlertaGPS.contract_code != None)
                       .order_by(AlertaGPS.contract_code).all()
    ]

    return jsonify({
        "grupos":           resultado,
        "total":            len(alertas),
        "pendientes":       pendientes,
        "codigos_contrato": todos_contratos,
    })

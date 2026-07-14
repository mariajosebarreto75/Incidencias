
import uuid
import os
import json
import re

from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    jsonify,
    send_from_directory,
    current_app
)
from werkzeug.utils import secure_filename

from flask_login import (
    login_required,
    current_user
)

from app.extensions import db

from app.models.distribucion_operativa import DistribucionOperativa
from app.models.recurso_contrato import RecursoContrato
from app.models.placa_contrato import PlacaContrato
from app.models.meta_operativa import MetaOperativa
from app.models.actividad import Actividad
from app.models.accion_tomar import AccionTomar
from app.models.parametro_coor import ParametroCoor
from app.models.reporte_operacional import ReporteOperacional

from app.models.persona import (
    Persona
)
from datetime import (
    datetime,
    timedelta,
    time as dt_time
)
from app.models.contrato import (
    Contrato
)
from app.models.user import User
from app.models.user_contrato import UserContrato
from app.routes.notificaciones import crear_notificacion

coordinador = Blueprint(
    "coordinador",
    __name__
)


def parsear_hora(valor):
    if not valor:
        return None
    try:
        partes = str(valor).strip().split(":")
        return dt_time(
            int(partes[0]),
            int(partes[1]),
            int(partes[2]) if len(partes) > 2 else 0
        )
    except Exception:
        return None


def parsear_meta(valor):
    if not valor:
        return None
    try:
        # "2.457.051" â†’ quitar puntos de miles â†’ float
        return float(str(valor).strip().replace(".", "").replace(",", "."))
    except Exception:
        return None


def formatear_coordenada(valor, posicion_coma):
    """
    Normaliza coordenadas al formato con coma decimal.
    Casos:
      - Ya tiene coma            â†’ devuelve tal cual
      - Tiene punto real decimal â†’ reemplaza punto por coma  (-74.638 â†’ -74,638)
      - Float .0 de pandas       â†’ trata como entero         (-4493839.0 â†’ -44,93839)
      - Entero puro              â†’ inserta coma en posiciÃ³n   36364567 â†’ 3,6364567
    """
    if not valor:
        return ""
    s = str(valor).strip()
    if not s or s.lower() in ("nan", "none", ""):
        return ""

    # Ya tiene coma: listo
    if "," in s:
        return s

    # Tiene punto: puede ser decimal real o .0 de pandas
    if "." in s:
        partes = s.split(".")
        decimal = partes[1].rstrip("0")
        if not decimal:
            # Es X.0 o X.000 â†’ tratar como entero
            s = partes[0]
        else:
            # Decimal real: reemplazar punto por coma
            return s.replace(".", ",")

    # Entero puro: insertar coma en posicion_coma
    negativo = s.startswith("-")
    digitos  = s[1:] if negativo else s

    if not re.match(r'^\d+$', digitos):
        return s

    if len(digitos) <= posicion_coma:
        return s

    formateado = digitos[:posicion_coma] + "," + digitos[posicion_coma:]
    return ("-" + formateado) if negativo else formateado


# =====================================
# DASHBOARD COORDINADOR
# =====================================

@coordinador.route(
    "/coordinador"
)
@login_required
def dashboard_coordinador():

    return render_template(
        "coordinador/dashboard.html"
    )


# =====================================
# PANEL REPORTES
# =====================================

ESTADOS_CONFORMIDAD = [
    "Conforme",
    "No conforme",
]

_PARAMETROS_COOR_SEED = [
    "Operativo",
    "Seguridad",
    "Calidad de servicio",
    "Eficiencia",
    "Conducta",
    "Otro",
]

_EXT_COOR = {"jpg", "jpeg", "png", "webp", "gif"}
_MAX_MB   = 10


def _ext_ok_coor(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in _EXT_COOR


@coordinador.route("/coordinador/PanelReportes")
@coordinador.route("/coordinador/panelReportes")
@login_required
def panel_reportes():

    _uc = UserContrato.query.filter_by(user_id=current_user.id).all()
    if _uc:
        _nombres_uc = [uc.contrato for uc in _uc]
        lista_contratos = [c.contrato for c in
                           Contrato.query.filter(Contrato.contrato.in_(_nombres_uc),
                                                 Contrato.activo == True).all()]
    else:
        lista_contratos = [c.contrato for c in Contrato.query.filter_by(
            coordinador=current_user.nombre_completo, activo=True
        ).all()]

    contrato_filtro = request.args.get("contrato",    "").strip()
    fecha_ini_str   = request.args.get("fecha_ini",   "").strip()
    fecha_fin_str   = request.args.get("fecha_fin",   "").strip()
    recurso_filtro  = request.args.get("recurso",     "").strip()

    query = ReporteOperacional.query
    if lista_contratos:
        query = query.filter(ReporteOperacional.contrato.in_(lista_contratos))

    if contrato_filtro and contrato_filtro in lista_contratos:
        query = query.filter(ReporteOperacional.contrato == contrato_filtro)

    if fecha_ini_str:
        try:
            fi = datetime.strptime(fecha_ini_str, "%Y-%m-%d").date()
            query = query.filter(ReporteOperacional.fecha_reporte >= fi)
        except ValueError:
            pass

    if fecha_fin_str:
        try:
            ff = datetime.strptime(fecha_fin_str, "%Y-%m-%d").date()
            query = query.filter(ReporteOperacional.fecha_reporte <= ff)
        except ValueError:
            pass

    if recurso_filtro:
        query = query.filter(
            ReporteOperacional.recurso.ilike(f"%{recurso_filtro}%")
        )

    # Recursos distintos del coordinador (para el select del filtro)
    recursos_disponibles = (
        db.session.query(ReporteOperacional.recurso)
        .filter(ReporteOperacional.contrato.in_(lista_contratos))
        .distinct()
        .order_by(ReporteOperacional.recurso)
        .all()
    )
    lista_recursos = [r[0] for r in recursos_disponibles if r[0]]

    reportes = query.order_by(ReporteOperacional.fecha_creado.desc()).all()

    return render_template(
        "coordinador/panel_reportes.html",
        reportes             = reportes,
        lista_contratos      = lista_contratos,
        contrato_activo      = contrato_filtro or "todos",
        lista_recursos       = lista_recursos,
        filtros = {
            "fecha_ini":  fecha_ini_str,
            "fecha_fin":  fecha_fin_str,
            "recurso":    recurso_filtro,
            "contrato":   contrato_filtro,
        }
    )


# =====================================
# DISTRIBUCION OPERATIVA
# =====================================

@coordinador.route("/coordinador/plan/sincronizar", methods=["POST"])
@login_required
def sincronizar_plan_gps():
    """Sincroniza el plan del dÃ­a desde GPS Monitor para la fecha solicitada."""
    from app.services.sincronizar_plan import sincronizar_plan
    datos = request.get_json(silent=True) or {}
    from_date = datos.get("desde") or datos.get("fecha") or None
    to_date   = datos.get("hasta") or datos.get("fecha_fin") or from_date
    resultado = sincronizar_plan(from_date, to_date)
    if "error" in resultado:
        return jsonify({"ok": False, "error": resultado["error"]})
    return jsonify({"ok": True, **resultado})


@coordinador.route(
    "/coordinador/distribucion-operativa",
    methods=["GET"]
)
@login_required
def distribucion_operativa():

    from datetime import date as _date

    # Filtros de la URL
    fecha_desde_str = request.args.get("fecha_desde") or str(_date.today())
    fecha_hasta_str = request.args.get("fecha_hasta") or fecha_desde_str
    contrato_filtro = request.args.get("contrato") or ""

    try:
        fecha_desde = datetime.strptime(fecha_desde_str, "%Y-%m-%d").date()
        fecha_hasta = datetime.strptime(fecha_hasta_str, "%Y-%m-%d").date()
    except ValueError:
        fecha_desde = fecha_hasta = _date.today()
        fecha_desde_str = fecha_hasta_str = str(_date.today())

    # Contratos del coordinador (objetos completos para obtener nombre y código)
    _uc2 = UserContrato.query.filter_by(user_id=current_user.id).all()
    if _uc2:
        _nombres_uc2 = [uc.contrato for uc in _uc2]
        _contratos_obj = Contrato.query.filter(
            Contrato.contrato.in_(_nombres_uc2), Contrato.activo == True
        ).all()
    else:
        _contratos_obj = Contrato.query.filter_by(
            coordinador=current_user.nombre_completo, activo=True
        ).all()

    lista_contratos = [c.contrato for c in _contratos_obj]
    # Incluir códigos cortos (ej: "021C") para que los registros de GPS Monitor
    # que no resolvieron al nombre completo también aparezcan
    lista_codigos   = [c.codigo for c in _contratos_obj if c.codigo]
    lista_valores   = list(set(lista_contratos + lista_codigos))

    # Consultar registros con filtros
    q = DistribucionOperativa.query.filter(
        DistribucionOperativa.fecha.between(fecha_desde, fecha_hasta)
    )
    if lista_valores:
        q = q.filter(DistribucionOperativa.contrato.in_(lista_valores))
    if contrato_filtro and contrato_filtro in lista_valores:
        q = q.filter(DistribucionOperativa.contrato == contrato_filtro)
    registros = q.order_by(DistribucionOperativa.fecha.asc(), DistribucionOperativa.id.asc()).all()

    # Lookup personas
    cedulas = list({r.cedula_1 for r in registros if r.cedula_1})
    personas_map = {
        p.Documento: p
        for p in Persona.query.filter(Persona.Documento.in_(cedulas)).all()
    } if cedulas else {}

    datos_tabla = []
    for r in registros:
        persona = personas_map.get(r.cedula_1)
        datos_tabla.append({
            "id":               r.id,
            "fecha":            str(r.fecha),
            "contrato":         r.contrato,
            "recurso":          r.recurso or "",
            "placa":            r.placa or "",
            "orden_trabajo":    r.orden_trabajo or "",
            "tipo_actividad":   r.tipo_actividad or "",
            "tipo_cuadrilla":   r.tipo_cuadrilla or "",
            "cedula_1":         r.cedula_1 or "",
            "nombre_1":         persona.Nombre if persona else "",
            "cargo_1":          persona.Cargo  if persona else "",
            "cedula_2":         r.cedula_2 or "",
            "cedula_3":         r.cedula_3 or "",
            "cedula_4":         r.cedula_4 or "",
            "cedula_5":         r.cedula_5 or "",
            "duracion_actividad": r.duracion_actividad or "",
            "latitud":          r.latitud or "",
            "longitud":         r.longitud or "",
            "observacion":      r.observacion or "",
            "origen":           r.origen or "manual",
        })

    return render_template(
        "coordinador/distribucion_operativa.html",
        datos_tabla=json.dumps(datos_tabla, ensure_ascii=False),
        contratos=json.dumps(lista_valores, ensure_ascii=False),
        fecha_desde=fecha_desde_str,
        fecha_hasta=fecha_hasta_str,
        contrato_filtro=contrato_filtro,
    )


# =====================================
# CUADRILLAS POR CONTRATO
# =====================================

@coordinador.route(
    "/coordinador/cuadrillas/<path:contrato>"
)
@login_required
def obtener_cuadrillas(contrato):

    cuadrillas = (
        db.session.query(
            MetaOperativa.Tipo_cuadrilla
        )
        .filter(
            MetaOperativa.contrato == contrato
        )
        .distinct()
        .all()
    )

    return jsonify([
        c[0]
        for c in cuadrillas
    ])    
# =====================================
# META POR CONTRATO Y CUADRILLA
# =====================================

@coordinador.route(
    "/coordinador/meta/<path:contrato>/<path:cuadrilla>"
)
@login_required
def obtener_meta(
    contrato,
    cuadrilla
):

    meta = (
        MetaOperativa.query.filter(
            MetaOperativa.contrato == contrato,
            db.func.lower(db.func.trim(MetaOperativa.Tipo_cuadrilla))
            == cuadrilla.lower().strip()
        ).first()
    )

    if not meta:

        return jsonify({

            "meta": ""

        })

    return jsonify({

        "meta": round(
            meta.Meta_Produccion
        )

    })


# =====================================
# BUSCAR PERSONA
# =====================================

@coordinador.route(
    "/coordinador/buscar-persona/<cedula>"
)
@login_required
def buscar_persona(cedula):

    persona = (
        Persona.query.filter_by(
            Documento=cedula
        ).first()
    )

    if not persona:

        return jsonify({

            "success": False

        })

    return jsonify({

        "success": True,

        "nombre": persona.Nombre,

        "cargo": persona.Cargo,

        "salario": persona.Salario

    })


# =====================================
# CREAR PERSONA
# =====================================

@coordinador.route(
    "/coordinador/crear-persona",
    methods=["POST"]
)
@login_required
def crear_persona():

    try:

        datos = request.get_json()

        documento = str(datos.get("documento", "")).strip()
        nombre    = str(datos.get("nombre",    "")).strip()
        cargo     = str(datos.get("cargo",     "")).strip()
        salario_raw = datos.get("salario")

        if not documento or not nombre or not cargo:
            return jsonify({
                "success": False,
                "mensaje": "Documento, nombre y cargo son obligatorios."
            }), 400

        existe = Persona.query.filter_by(
            Documento=documento
        ).first()

        if existe:
            return jsonify({
                "success": False,
                "mensaje": f"La cÃ©dula {documento} ya estÃ¡ registrada."
            }), 400

        salario = None
        if salario_raw:
            try:
                salario = float(
                    str(salario_raw)
                    .replace(".", "")
                    .replace(",", ".")
                )
            except Exception:
                pass

        nueva = Persona(
            Documento=documento,
            Nombre=nombre,
            Cargo=cargo,
            Salario=salario
        )

        db.session.add(nueva)
        db.session.commit()

        return jsonify({
            "success": True,
            "mensaje": f"Persona '{nombre}' creada correctamente.",
            "nombre":  nombre,
            "cargo":   cargo
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({
            "success": False,
            "mensaje": str(e)
        }), 500


# =====================================
# DETALLE + RESPUESTA
# =====================================

@coordinador.route("/coordinador/reporte/<int:id>")
@login_required
def detalle_reporte(id):

    reporte = ReporteOperacional.query.get_or_404(id)

    acciones_db    = [a.accion for a in AccionTomar.query.order_by(AccionTomar.accion).all()]
    parametros_db  = [p.parametro for p in ParametroCoor.query.order_by(ParametroCoor.parametro).all()]

    # Nombre completo del usuario que reportÃ³
    reportador = User.query.filter_by(username=reporte.reportado_por).first()
    nombre_reportado = reportador.nombre_completo.title() if reportador else reporte.reportado_por

    return render_template(
        "coordinador/detalle_reporte.html",
        reporte             = reporte,
        estados_conformidad = ESTADOS_CONFORMIDAD,
        acciones_tomar      = acciones_db,
        parametros_coor     = parametros_db,
        nombre_reportado    = nombre_reportado,
    )


# =====================================
# GUARDAR RESPUESTA
# =====================================

@coordinador.route("/coordinador/reporte/<int:id>/responder", methods=["POST"])
@login_required
def responder_reporte(id):

    reporte = ReporteOperacional.query.get_or_404(id)
    datos   = request.get_json()

    requeridos = {
        "respuesta":          "Respuesta",
        "estado_conformidad": "Estado de conformidad",
        "accion_a_tomar":     "AcciÃ³n a tomar",
        "evidencia_coor_1":   "Evidencia 1 del coordinador",
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

    reporte.respuesta            = datos["respuesta"]
    reporte.parametro_coordinador = datos.get("parametro_coordinador") or None
    reporte.evidencia_coor_1     = datos["evidencia_coor_1"]
    reporte.evidencia_coor_2     = datos.get("evidencia_coor_2") or None
    reporte.estado_conformidad   = datos["estado_conformidad"]
    reporte.accion_a_tomar       = datos["accion_a_tomar"]
    reporte.respondido_por       = current_user.nombre_completo
    reporte.fecha_respuesta      = datetime.now()
    reporte.estado               = "Respondido"

    try:
        db.session.commit()
        # Notificar al NEO que reportÃ³
        crear_notificacion(reporte.reportado_por, "reporte_respondido", reporte)
        db.session.commit()
        return jsonify({
            "success": True,
            "mensaje": f"Reporte #{reporte.id} respondido correctamente."
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "mensaje": str(e)}), 500


# =====================================
# SUBIR EVIDENCIA COORDINADOR
# =====================================

@coordinador.route("/coordinador/subir-evidencia-coor", methods=["POST"])
@login_required
def subir_evidencia_coor():

    archivo = request.files.get("archivo")

    if not archivo or not archivo.filename:
        return jsonify({"success": False, "mensaje": "No se recibiÃ³ archivo."}), 400

    if not _ext_ok_coor(archivo.filename):
        return jsonify({
            "success": False,
            "mensaje": "Tipo no permitido. Use JPG, PNG o WEBP."
        }), 400

    archivo.seek(0, 2)
    if archivo.tell() / (1024 * 1024) > _MAX_MB:
        return jsonify({"success": False, "mensaje": f"Supera {_MAX_MB} MB."}), 400
    archivo.seek(0)

    ahora  = datetime.now()
    anio   = str(ahora.year)
    mes    = str(ahora.month).zfill(2)
    ext    = secure_filename(archivo.filename).rsplit(".", 1)[1].lower()
    nombre = f"{ahora.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.{ext}"

    directorio = os.path.join(
        current_app.root_path, "uploads", "evidencias_coor", anio, mes
    )
    os.makedirs(directorio, exist_ok=True)
    archivo.save(os.path.join(directorio, nombre))

    ruta = f"uploads/evidencias_coor/{anio}/{mes}/{nombre}"

    return jsonify({
        "success": True,
        "ruta":    ruta,
        "url":     f"/coordinador/evidencia-coor/{ruta}"
    })


# =====================================
# SERVIR IMAGEN COORDINADOR
# =====================================

@coordinador.route("/coordinador/evidencia-coor/<path:ruta>")
@login_required
def ver_evidencia_coor(ruta):

    ruta_abs = os.path.join(current_app.root_path, ruta)
    return send_from_directory(os.path.dirname(ruta_abs), os.path.basename(ruta_abs))

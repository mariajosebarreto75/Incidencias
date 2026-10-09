import os
import uuid

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    send_from_directory,
    current_app,
    abort,
    redirect,
    url_for,
)

from flask_login import (
    login_required,
    current_user
)

from datetime import datetime, timedelta
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
from app.routes.notificaciones import crear_notificacion, coordinadores_de_contrato


neo = Blueprint("neo", __name__)

# Afectación económica: (meta / HORAS_DIA_ESTANDAR) × horas_afectadas
# Debe coincidir con la fórmula usada al crear el reporte (app/static/js/neo/PanelNeo.js)
HORAS_DIA_ESTANDAR = 7.33



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
MAX_MB = 20


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


def _tipo_sin_duracion(tipo_incidencia):
    """Tipos que no tienen hora inicio/fin y no deben calcular duración ni afectación."""
    import unicodedata
    def _n(s):
        return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower().strip()
    SIN_DURACION = {"error en la informacion"}
    return _n(tipo_incidencia) in SIN_DURACION


def _calcular_impacto(tipo_incidencia, diff_min=0):
    """Retorna 'Alto', 'Medio', 'Bajo' o None según el tipo de incidencia."""
    import unicodedata
    def _norm(s):
        return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower().strip()
    tipo_n = _norm(tipo_incidencia or "")
    impactos_altos = {
        _norm(t) for t in [
            "fuera de ruta", "tiempo muerto", "inicio tardio de labores",
            "salida tardia", "finalizacion temprana",
            "error en la informacion", "mal enrutamiento"
        ]
    }
    if tipo_n in impactos_altos:
        return "Alto"
    if "excede tiempo" in tipo_n:
        if diff_min < 15:
            return "Bajo"
        elif diff_min < 25:
            return "Medio"
        return "Alto"
    return None


def _parsear_float(valor):
    if not valor:
        return None
    try:
        s = str(valor).strip()
        # Si tiene coma y punto: formato europeo 1.234,56 → quitar punto, cambiar coma
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        # Solo coma como separador decimal: 1234,56 → 1234.56
        elif "," in s:
            s = s.replace(",", ".")
        # Solo puntos: ya es formato estándar (1234.56)
        return float(s)
    except (ValueError, TypeError):
        return None


def _normalizar_cuadrilla(s):
    """Minúsculas y sin espacios (ni internos): 'CUAD (MTTO)' y 'CUAD(MTTO)' deben matchear."""
    import re
    return re.sub(r"\s+", "", (s or "").lower())


def _buscar_meta_operativa(contrato, tipo_cuadrilla):
    """Busca la meta oficial en la tabla metas_operativas por (contrato, tipo_cuadrilla).
    Es la fuente de verdad: evita depender del valor de meta tecleado/formateado en el
    frontend, que puede llegar vacío o mal parseado (ej. '452.499' interpretado como
    decimal en vez de miles)."""
    if not contrato or not tipo_cuadrilla:
        return None
    contrato_norm = contrato.strip().lower()
    tc_norm = _normalizar_cuadrilla(tipo_cuadrilla)
    candidatas = MetaOperativa.query.filter(
        db.func.lower(db.func.trim(MetaOperativa.contrato)) == contrato_norm
    ).all()
    for m in candidatas:
        if _normalizar_cuadrilla(m.Tipo_cuadrilla) == tc_norm:
            return m.Meta_Produccion
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
    mostrar_todo    = request.args.get("todo") == "1"

    if mostrar_todo:
        fecha_desde = fecha_hasta = None
        fecha_desde_str = fecha_hasta_str = ""
    elif fecha_desde_str:
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

    q = DistribucionOperativa.query
    if not mostrar_todo:
        q = q.filter(DistribucionOperativa.fecha.between(fecha_desde, fecha_hasta))
    registros = q.order_by(DistribucionOperativa.fecha.asc(), DistribucionOperativa.id.asc()).all()

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
    u = current_user
    if u.rol.lower() not in ("neo", "admin"):
        abort(403)
    es_admin = u.rol.lower() == "admin"
    dash = es_admin or u.acceso_dashboard

    groups = [
        {
            "name": "Reportar y Operación", "icon": "bi-broadcast-pin", "tint": "#0891B2",
            "links": [
                {"label": "Reportar", "icon": "bi-clipboard2-pulse-fill", "url": url_for("neo.panel_reportes"),
                 "desc": "Registrar una incidencia operativa de campo"},
                {"label": "Validar Reportes", "icon": "bi-patch-check-fill", "url": url_for("neo.validar_reportes"),
                 "desc": "Revisar y calificar reportes del equipo"},
                {"label": "Distribución Operativa", "icon": "bi-table", "url": url_for("neo.distribucion_neo"),
                 "desc": "Programación diaria de cuadrillas y recursos"},
            ],
        },
    ]

    he_items = []
    if u.tiene_permiso("horas_extras") or es_admin:
        he_items.append({"label": "Registro / Validación", "icon": "bi-pencil-square", "url": "/horas-extras",
                          "desc": "Ingreso y validación de horas extras"})
    if u.tiene_permiso("dashboard_he") or dash:
        he_items.append({"label": "Dashboard HE", "icon": "bi-bar-chart-line-fill", "url": url_for("he_bp.he_dashboard"),
                          "desc": "KPIs, tipos de HE, límite legal y valor de nómina"})
    if he_items:
        groups.append({"name": "Horas Extras", "icon": "bi-clock-history", "tint": "#8B5CF6", "links": he_items})

    if u.tiene_permiso("indicadores") or es_admin:
        groups[0]["links"].append({
            "label": "Indicadores", "icon": "bi-speedometer2",
            "url": url_for("dashboard.indicadores"),
            "desc": "Dashboard gerencial de KPIs: reportes, horas extras y compromisos",
        })

    seg_items = []
    if u.tiene_permiso("bi_seguimiento"):
        seg_items.append({"label": "Archivo de Seguimiento", "icon": "bi-folder2-open", "url": url_for("coordinador.bi_seguimiento"),
                           "desc": "Informe operacional de seguimiento (Power BI)"})
    if u.tiene_permiso("bi_inspecciones"):
        seg_items.append({"label": "Inspecciones", "icon": "bi-search",
                           "url": "https://app.powerbi.com/view?r=eyJrIjoiYWYwYmRhZWQtOWYzNC00OWYxLWJkM2MtZGU5ZTk5MDU4ZTMxIiwidCI6ImU1NjkzYWJkLWViMTEtNDk5Mi05OGE5LThhNjRhODJkNTRhYiJ9",
                           "ext": True, "desc": "Indicador de inspecciones (Power BI)"})
    if u.tiene_permiso("preoperacionales") or u.tiene_permiso("preoperacionales_dashboard") or dash:
        seg_items.append({"label": "Preoperacionales", "icon": "bi-clipboard-check-fill", "url": url_for("neo.preoperacionales_neo"),
                           "desc": "Cumplimiento, estado de vehículos y placas"})
    if u.tiene_permiso("semaforo"):
        seg_items.append({"label": "Semáforo (calificar)", "icon": "bi-stoplights-fill",
                           "url": url_for("coordinador.semaforo_dashboard"),
                           "desc": "Registra calificaciones de actividades por contrato"})
    if u.tiene_permiso("semaforo_dashboard"):
        seg_items.append({"label": "Semáforo Dashboard", "icon": "bi-bar-chart-steps",
                           "url": url_for("coordinador.semaforo_dashboard"),
                           "desc": "Visualiza el estado del semáforo sin calificar"})
    if seg_items:
        groups.append({"name": "Seguimiento y Calidad", "icon": "bi-clipboard2-data", "tint": "#16A34A", "links": seg_items})

    if u.tiene_permiso("gps") or es_admin:
        groups.append({
            "name": "GPS", "icon": "bi-geo-alt-fill", "tint": "#DC2626",
            "links": [
                {"label": "Rastrear", "icon": "bi-map", "url": "https://plataforma.sistemagps.online/ui/map/objects",
                 "ext": True, "desc": "Mapa de vehículos en vivo"},
            ],
        })

    groups.append({
        "name": "Compromisos", "icon": "bi-calendar-check", "tint": "#D97706",
        "links": [
            {"label": "Reuniones", "icon": "bi-calendar3", "url": url_for("compromisos.reuniones"),
             "desc": "Programación de reuniones por contrato"},
            {"label": "Checklist", "icon": "bi-list-check", "url": url_for("compromisos.checklist"),
             "desc": "Checklist de reuniones realizadas"},
            {"label": "Agenda", "icon": "bi-journal-check", "url": url_for("compromisos.lista"),
             "desc": "Compromisos pendientes y atrasados"},
        ],
    })

    return render_template(
        "portal/home.html",
        page_title="NEO",
        page_desc="Módulo NEO — gestión de incidencias operativas de campo",
        intro_title=f"Hola, {current_user.nombre_completo.title()}",
        intro_sub="Módulo NEO — Gestión de incidencias operativas de campo",
        groups=groups,
        home_endpoint=None,
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
    recursos_f    = [v.strip() for v in request.args.getlist("recurso") if v.strip()]
    contratos_f   = [v.strip() for v in request.args.getlist("contrato") if v.strip()]

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
    if recursos_f:
        q = q.filter(ReporteOperacional.recurso.in_(recursos_f))
    if contratos_f:
        q = q.filter(ReporteOperacional.contrato.in_(contratos_f))

    reportes = q.order_by(ReporteOperacional.fecha_creado.desc()).all()

    # Listas para los selectores de filtro — usar la misma visibilidad que el query principal
    if asignados:
        q_todos = ReporteOperacional.query.filter(
            ReporteOperacional.contrato.in_(contratos_visibles)
        )
    else:
        q_todos = ReporteOperacional.query.filter_by(reportado_por=current_user.username)

    todos = (
        q_todos
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
        "recursos":      recursos_f,
        "contratos":     contratos_f,
    }

    kpis = {
        "total":        len(reportes),
        "pendientes":   sum(1 for r in reportes if r.conformidad_neo not in ("Conforme", "No conforme", "Consiliado") and r.estado != "Respondido"),
        "no_conformes": sum(1 for r in reportes if r.conformidad_neo == "No conforme"),
        "conformes":    sum(1 for r in reportes if r.conformidad_neo == "Conforme"),
        "consiliados":  sum(1 for r in reportes if r.conformidad_neo == "Consiliado"),
    }

    return render_template(
        "neo/validar_reportes.html",
        reportes=reportes,
        lista_contratos=lista_contratos,
        lista_recursos=lista_recursos,
        filtros=filtros,
        kpis=kpis,
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
    asignados = UserContrato.query.filter_by(user_id=current_user.id).all()
    if asignados:
        contratos_visibles = [uc.contrato for uc in asignados]
        if reporte.contrato not in contratos_visibles:
            abort(403)
    elif reporte.reportado_por != current_user.username:
        abort(403)
    if reporte.estado == "Cerrado":
        return jsonify({
            "ok": False,
            "error": "Este reporte fue cerrado tras la apelación del coordinador y ya no admite cambios."
        }), 400
    if reporte.estado != "Respondido":
        return jsonify({"ok": False, "error": "El coordinador aún no ha respondido"}), 400

    datos = request.get_json()
    conformidad = (datos.get("conformidad_neo") or "").strip()
    obs = (datos.get("observacion_conformidad") or "").strip()

    if conformidad not in ("Conforme", "No conforme", "Consiliado"):
        return jsonify({"ok": False, "error": "Seleccione un valor de conformidad"}), 400

    reporte.conformidad_neo = conformidad
    reporte.observacion_conformidad = obs or None
    db.session.commit()

    # Notificar al coordinador si es No conforme o Consiliado
    if conformidad in ("No conforme", "Consiliado"):
        for coor in coordinadores_de_contrato(reporte.contrato):
            crear_notificacion(coor, "no_conforme", reporte)
        db.session.commit()

    return jsonify({"ok": True})


# ── Subir evidencia de conformidad (imagen opcional) ─────────────────────────
_ALLOWED_IMG_NEO = {"png", "jpg", "jpeg", "gif", "webp"}

@neo.route("/neo/reporte/<int:id>/evidencia", methods=["POST"])
@login_required
def evidencia_reporte(id):
    reporte = ReporteOperacional.query.get_or_404(id)
    f = request.files.get("imagen")
    if f and f.filename:
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext in _ALLOWED_IMG_NEO:
            folder = os.path.join(current_app.root_path, "static", "uploads", "reporte_evidencias")
            os.makedirs(folder, exist_ok=True)
            nombre = f"{id}_conf_{uuid.uuid4().hex[:8]}.{ext}"
            f.save(os.path.join(folder, nombre))
            reporte.evidencia_conformidad = f"uploads/reporte_evidencias/{nombre}"
            from app.extensions import db
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
    asignados = UserContrato.query.filter_by(user_id=current_user.id).all()
    if asignados:
        contratos_visibles = [uc.contrato for uc in asignados]
        if reporte.contrato not in contratos_visibles:
            abort(403)
    elif reporte.reportado_por != current_user.username:
        abort(403)

    if request.method == "POST":
        if reporte.estado == "Cerrado":
            return jsonify({
                "ok": False,
                "error": "Este reporte fue cerrado tras la apelación del coordinador y ya no admite cambios."
            }), 400

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
        if reporte.hora_inicio and reporte.hora_fin and not _tipo_sin_duracion(reporte.tipo_incidencia):
            dt_ini = datetime.combine(_date.today(), reporte.hora_inicio)
            dt_fin = datetime.combine(_date.today(), reporte.hora_fin)
            if dt_fin <= dt_ini:
                dt_fin += timedelta(days=1)
            diff_min = int((dt_fin - dt_ini).total_seconds() // 60)
            h, m = divmod(diff_min, 60)
            reporte.duracion = f"{h}h {m:02d}m"
            reporte.horas_afectadas = round(diff_min / 60, 6)
        elif _tipo_sin_duracion(reporte.tipo_incidencia):
            reporte.duracion = None
            reporte.horas_afectadas = None
            reporte.afectacion_economica = None

        # Campos texto
        for campo in ("placa", "tipo_actividad", "tipo_cuadrilla",
                      "tipo_incidencia", "parametro_neo", "observacion",
                      "recurso"):
            if campo in d:
                setattr(reporte, campo, d[campo] or None)

        # Recalcular impacto
        impacto_calc = _calcular_impacto(reporte.tipo_incidencia, diff_min)
        if impacto_calc:
            reporte.impacto = impacto_calc

        # Meta: si cambió el contrato o el tipo de cuadrilla, tomar el valor oficial
        # del catálogo de metas operativas en vez de confiar en texto tecleado
        if "tipo_cuadrilla" in d or "contrato" in d:
            meta_catalogo = _buscar_meta_operativa(reporte.contrato, reporte.tipo_cuadrilla)
            if meta_catalogo is not None:
                reporte.meta = meta_catalogo

        # Caso sede/salida tardía: meta = numero_recursos * meta_promedio, siempre
        # (estos campos no son editables aquí, así que el valor recalculado es confiable)
        if reporte.numero_recursos and reporte.meta_promedio:
            reporte.meta = reporte.numero_recursos * reporte.meta_promedio

        # Recalcular afectación económica solo si el cliente no envió un valor
        if "afectacion" in d and d["afectacion"] not in (None, ""):
            reporte.afectacion_economica = _parsear_float(d["afectacion"])
        elif reporte.meta and reporte.horas_afectadas:
            reporte.afectacion_economica = (
                (reporte.meta / HORAS_DIA_ESTANDAR) * reporte.horas_afectadas
            )

        # Evidencias (solo si se subió algo nuevo)
        if d.get("evidencia_1"):
            reporte.evidencia_1 = d["evidencia_1"]
        if "evidencia_2" in d:
            reporte.evidencia_2 = d["evidencia_2"] or None

        reporte.editado_por = current_user.username
        reporte.fecha_edicion = datetime.now()

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

    return render_template(
        "neo/panelReportes.html",
        tipos_desvio   = tipos_desvio,
        parametros_neo = parametros_neo,
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

    # Precargar todas las metas del contrato para lookup client-side
    todas_metas = MetaOperativa.query.filter_by(contrato=contrato).all()
    metas_map = {
        m.Tipo_cuadrilla.strip().lower(): "{:,.0f}".format(m.Meta_Produccion).replace(",", ".")
        for m in todas_metas if m.Tipo_cuadrilla
    }

    return jsonify({"success": True, "ordenes": ordenes, "metas": metas_map})


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

    numero_recursos_val = int(datos["numero_recursos"]) if datos.get("numero_recursos") else None
    meta_promedio_val   = _parsear_float(datos.get("meta_promedio"))
    tipo_incidencia_txt = datos.get("tipo_incidencia_nombre") or datos.get("tipo_incidencia", "")
    sin_duracion         = _tipo_sin_duracion(tipo_incidencia_txt)

    meta_val = None if sin_duracion else (
        _buscar_meta_operativa(datos.get("contrato"), datos.get("tipo_cuadrilla"))
        or (numero_recursos_val * meta_promedio_val if numero_recursos_val and meta_promedio_val else None)
        or _parsear_float(datos.get("meta"))
    )
    horas_afectadas_val = None if sin_duracion else (
        _parsear_float(datos.get("horas_afectadas"))
    )
    duracion_val = datos.get("duracion") or None
    if not sin_duracion and hora_inicio and hora_fin:
        _dt_ini = datetime.combine(fecha, hora_inicio)
        _dt_fin = datetime.combine(fecha, hora_fin)
        if _dt_fin <= _dt_ini:
            _dt_fin += timedelta(days=1)
        _diff_min = int((_dt_fin - _dt_ini).total_seconds() // 60)
        horas_afectadas_val = round(_diff_min / 60, 6)
        _h, _m = divmod(_diff_min, 60)
        duracion_val = f"{_h}h {_m:02d}m"
    afectacion_val = None if sin_duracion else (
        (meta_val / HORAS_DIA_ESTANDAR) * horas_afectadas_val
        if meta_val and horas_afectadas_val else
        _parsear_float(datos.get("afectacion"))
    )

    try:
        reporte = ReporteOperacional(
            fecha_reporte       = fecha,
            contrato            = datos["contrato"],
            recurso             = datos["recurso"],
            placa               = datos.get("placa")           or None,
            orden_trabajo       = datos.get("orden_trabajo")   or None,
            tipo_actividad      = datos.get("tipo_actividad")  or None,
            tipo_cuadrilla      = datos.get("tipo_cuadrilla")  or None,
            meta                = meta_val,
            hora_inicio         = hora_inicio,
            hora_fin            = hora_fin,
            # Guardamos el texto histórico, no el ID del catálogo
            tipo_incidencia     = datos.get("tipo_incidencia_nombre") or datos["tipo_incidencia"],
            parametro_neo       = datos.get("parametro_neo_nombre")   or "",
            observacion         = datos.get("observacion")            or "",
            duracion            = duracion_val,
            impacto             = datos.get("impacto") or _calcular_impacto(
                                      datos.get("tipo_incidencia_nombre") or datos.get("tipo_incidencia", "")
                                  ) or None,
            horas_afectadas     = horas_afectadas_val,
            afectacion_economica = afectacion_val,
            evidencia_1         = datos["evidencia_1"],
            evidencia_2         = datos.get("evidencia_2") or None,
            reportado_por       = current_user.username,
            estado              = "Abierto",
            numero_recursos     = numero_recursos_val,
            meta_promedio       = meta_promedio_val,
        )

        db.session.add(reporte)
        db.session.commit()

        # Notificar a coordinadores del contrato
        for coor in coordinadores_de_contrato(reporte.contrato):
            crear_notificacion(coor, "nuevo_reporte", reporte)
        db.session.commit()

        # Iniciar escalamiento si la incidencia es de tipo crítico
        try:
            from app.services.escalamiento_service import iniciar_escalamiento
            iniciar_escalamiento(reporte)
        except Exception as _esc_err:
            import logging
            logging.getLogger(__name__).error("Error iniciando escalamiento: %s", _esc_err)

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

        return jsonify({
            "success": True,
            "id":      reporte.id,
            "mensaje": f"Reporte #{reporte.id} guardado correctamente.",
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


@neo.route("/neo/api/reportes/actualizar-cuadrilla", methods=["POST"])
@login_required
def api_actualizar_cuadrilla():
    """Recibe JSON con lista de {id, tipo_cuadrilla}, actualiza cada reporte,
    busca la meta operativa y recalcula horas_afectadas y afectacion_economica."""
    from datetime import timedelta, date as _date
    datos = request.get_json() or {}
    filas = datos.get("filas", [])
    if not filas:
        return jsonify({"ok": False, "msg": "Sin datos"}), 400

    # Precargar metas en memoria: clave = (contrato.lower(), tipo_cuadrilla normalizada)
    metas = MetaOperativa.query.all()
    metas_map = {(m.contrato.strip().lower(), _normalizar_cuadrilla(m.Tipo_cuadrilla)): m.Meta_Produccion
                 for m in metas}

    actualizados = 0
    no_encontrados = []

    for f in filas:
        rid = f.get("id")
        tipo_cuadrilla = str(f.get("tipo_cuadrilla") or "").strip()
        if not rid:
            continue
        reporte = ReporteOperacional.query.get(int(rid))
        if not reporte:
            no_encontrados.append(rid)
            continue

        reporte.tipo_cuadrilla = tipo_cuadrilla or reporte.tipo_cuadrilla

        # Buscar meta operativa
        tc = _normalizar_cuadrilla(reporte.tipo_cuadrilla)
        clave = (reporte.contrato.strip().lower(), tc)
        meta_val = metas_map.get(clave)
        if meta_val is not None:
            reporte.meta = meta_val

        # Recalcular horas_afectadas desde hora_inicio y hora_fin
        if _tipo_sin_duracion(reporte.tipo_incidencia):
            reporte.duracion = None
            reporte.horas_afectadas = None
            reporte.afectacion_economica = None
        elif reporte.hora_inicio and reporte.hora_fin:
            dt_ini = datetime.combine(_date.today(), reporte.hora_inicio)
            dt_fin = datetime.combine(_date.today(), reporte.hora_fin)
            if dt_fin <= dt_ini:
                dt_fin += timedelta(days=1)
            diff_min = int((dt_fin - dt_ini).total_seconds() // 60)
            h, m = divmod(diff_min, 60)
            reporte.duracion = f"{h}h {m:02d}m"
            reporte.horas_afectadas = round(diff_min / 60, 6)

            # Recalcular afectación económica
            if reporte.meta and reporte.horas_afectadas:
                reporte.afectacion_economica = (reporte.meta / HORAS_DIA_ESTANDAR) * reporte.horas_afectadas

        actualizados += 1

    db.session.commit()
    return jsonify({"ok": True, "actualizados": actualizados, "no_encontrados": no_encontrados})


# =====================================
# DISTRIBUCIÓN OPERATIVA — CRUD MANUAL
# =====================================

@neo.route("/neo/distribucion-operativa/manual", methods=["POST"])
@login_required
def neo_distribucion_manual_crear():
    d = request.get_json(silent=True) or {}
    try:
        from datetime import datetime as _dt, time as _time
        def _t(v):
            if not v:
                return None
            try:
                parts = str(v).strip().split(":")
                return _time(int(parts[0]), int(parts[1]))
            except Exception:
                return None

        reg = DistribucionOperativa(
            fecha              = _dt.strptime(d["fecha"], "%Y-%m-%d").date() if d.get("fecha") else None,
            contrato           = str(d.get("contrato") or "").strip() or None,
            sede               = str(d.get("sede") or "").strip() or None,
            recurso            = str(d.get("recurso") or "").strip() or None,
            placa              = str(d.get("placa") or "").strip() or None,
            orden_trabajo      = str(d.get("orden_trabajo") or "").strip() or None,
            tipo_actividad     = str(d.get("tipo_actividad") or "").strip() or None,
            tipo_cuadrilla     = str(d.get("tipo_cuadrilla") or "").strip() or None,
            hora_salida_sede   = _t(d.get("hora_salida_sede")),
            hora_llegada_sede  = _t(d.get("hora_llegada_sede")),
            cedula_1           = str(d.get("cedula_1") or "").strip() or None,
            cedula_2           = str(d.get("cedula_2") or "").strip() or None,
            cedula_3           = str(d.get("cedula_3") or "").strip() or None,
            cedula_4           = str(d.get("cedula_4") or "").strip() or None,
            cedula_5           = str(d.get("cedula_5") or "").strip() or None,
            numero_celular     = str(d.get("numero_celular") or "").strip() or None,
            duracion_actividad = str(d.get("duracion_actividad") or "").strip() or None,
            observacion        = str(d.get("observacion") or "").strip() or None,
            origen             = "manual",
        )
        if not reg.fecha or not reg.contrato or not reg.recurso:
            return jsonify({"ok": False, "error": "Fecha, contrato y recurso son obligatorios"}), 422
        db.session.add(reg)
        db.session.commit()
        return jsonify({"ok": True, "id": reg.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@neo.route("/neo/distribucion-operativa/manual/<int:rid>", methods=["DELETE"])
@login_required
def neo_distribucion_manual_eliminar(rid):
    reg = DistribucionOperativa.query.get_or_404(rid)
    if reg.origen == "gps_monitor":
        return jsonify({"ok": False, "error": "No se pueden eliminar registros de GPS Monitor"}), 403
    db.session.delete(reg)
    db.session.commit()
    return jsonify({"ok": True})


@neo.route("/neo/distribucion-operativa/importar-excel", methods=["POST"])
@login_required
def neo_distribucion_importar_excel():
    import pandas as pd
    from datetime import datetime as _dt

    f = request.files.get("archivo")
    if not f:
        return jsonify({"ok": False, "error": "No se recibió archivo"}), 400
    try:
        df = pd.read_excel(f, dtype=str)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error leyendo Excel: {e}"}), 400

    # Alias: columnas del otro programador → campos del modelo
    _alias = {
        "recurso-cuadrilla":   "recurso",
        "tipobrigada":         "tipo_cuadrilla",
        "placa_vehiculo":      "placa",
        "punto_salida":        "hora_salida_sede",
        "hora_llegada_sede":   "hora_llegada_sede",
        "persona_#1":          "cedula_1",
        "persona_#2":          "cedula_2",
        "persona_#3":          "cedula_3",
        "persona_#4":          "cedula_4",
        "persona_#5":          "cedula_5",
        "orden_de_trabajo":    "orden_trabajo",
        "tipo_actividad":      "tipo_actividad",
        "duración_actividad":  "duracion_actividad",
        "duracion_actividad":  "duracion_actividad",
        "observación":         "observacion",
    }
    df.rename(columns=_alias, inplace=True)

    cols_req = {"fecha", "contrato", "recurso"}
    if not cols_req.issubset(set(df.columns)):
        faltantes = cols_req - set(df.columns)
        return jsonify({"ok": False, "error": f"Columnas faltantes: {', '.join(faltantes)}"}), 422

    def _s(row, col):
        v = row.get(col, "")
        if v is None or str(v).strip().lower() in ("", "nan", "none"):
            return None
        return str(v).strip()

    def _t(v):
        if not v:
            return None
        try:
            from datetime import time as _time
            parts = str(v).strip().split(":")
            return _time(int(parts[0]), int(parts[1]))
        except Exception:
            return None

    insertados = 0
    errores = []
    for i, row in df.iterrows():
        fila = i + 2
        try:
            fecha_str = _s(row, "fecha")
            if not fecha_str:
                errores.append(f"Fila {fila}: fecha vacía"); continue
            try:
                fecha = _dt.strptime(fecha_str[:10], "%Y-%m-%d").date()
            except Exception:
                try:
                    fecha = _dt.strptime(fecha_str[:10], "%d/%m/%Y").date()
                except Exception:
                    errores.append(f"Fila {fila}: fecha inválida '{fecha_str}'"); continue

            contrato = _s(row, "contrato")
            recurso  = _s(row, "recurso")
            if not contrato or not recurso:
                errores.append(f"Fila {fila}: contrato o recurso vacío"); continue

            db.session.add(DistribucionOperativa(
                fecha              = fecha,
                contrato           = contrato,
                sede               = _s(row, "sede"),
                recurso            = recurso,
                placa              = _s(row, "placa"),
                orden_trabajo      = _s(row, "orden_trabajo"),
                tipo_actividad     = _s(row, "tipo_actividad"),
                tipo_cuadrilla     = _s(row, "tipo_cuadrilla"),
                hora_salida_sede   = _t(_s(row, "hora_salida_sede")),
                hora_llegada_sede  = _t(_s(row, "hora_llegada_sede")),
                cedula_1           = _s(row, "cedula_1"),
                cedula_2           = _s(row, "cedula_2"),
                cedula_3           = _s(row, "cedula_3"),
                cedula_4           = _s(row, "cedula_4"),
                cedula_5           = _s(row, "cedula_5"),
                numero_celular     = _s(row, "numero_celular"),
                latitud            = _s(row, "latitud"),
                longitud           = _s(row, "longitud"),
                duracion_actividad = _s(row, "duracion_actividad"),
                observacion        = _s(row, "observacion"),
                origen             = "manual",
            ))
            insertados += 1
        except Exception as e:
            errores.append(f"Fila {fila}: {e}")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True, "insertados": insertados, "errores": errores})


# ── Preoperacionales (alias para usuarios NEO) ─────────────────
@neo.route("/neo/preoperacionales")
@login_required
def preoperacionales_neo():
    if not (current_user.tiene_permiso("preoperacionales") or current_user.tiene_permiso("preoperacionales_dashboard")):
        return redirect(url_for("neo.home_neo"))
    return render_template("coordinador/preoperacionales.html")


# =====================================
# HOME ROLES AUXILIARES
# =====================================

@neo.route("/home")
@login_required
def home_otros():
    """Home genérico para roles sin dashboard propio (administrativo, analista, sst, etc.)."""
    u = current_user
    rol = u.rol.lower()
    # Si el rol tiene un home específico, redirigir
    if rol == "admin":
        return redirect(url_for("admin_bp.dashboard"))
    if rol == "coordinador":
        return redirect(url_for("coordinador.dashboard_coordinador"))
    if rol == "neo":
        return redirect(url_for("neo.home_neo"))
    if rol == "director":
        return redirect(url_for("dashboard.director"))
    if rol == "supervisor":
        return redirect(url_for("coordinador.dashboard_supervisor"))
    if rol == "gerente":
        return redirect(url_for("dashboard.dashboards_hub"))

    es_admin = False
    groups = []

    # Módulos según permisos asignados individualmente
    rep_items = []
    if u.tiene_permiso("neo_reportes"):
        rep_items.append({"label": "Panel de Reportes NEO", "icon": "bi-clipboard-data-fill",
                           "url": url_for("coordinador.panel_reportes"),
                           "desc": "Valide y gestione reportes operacionales"})
    if rep_items:
        groups.append({"name": "Reportar y Operación", "icon": "bi-broadcast-pin",
                        "tint": "#0891B2", "links": rep_items})

    he_items = []
    if u.tiene_permiso("horas_extras"):
        he_items.append({"label": "Registro / Validación", "icon": "bi-pencil-square",
                          "url": "/horas-extras", "desc": "Ingreso y validación de horas extras"})
    if u.tiene_permiso("dashboard_he"):
        he_items.append({"label": "Dashboard HE", "icon": "bi-bar-chart-line-fill",
                          "url": url_for("he_bp.he_dashboard"),
                          "desc": "KPIs, tipos de HE, límite legal y valor de nómina"})
    if he_items:
        groups.append({"name": "Horas Extras", "icon": "bi-clock-history",
                        "tint": "#8B5CF6", "links": he_items})

    if u.tiene_permiso("indicadores"):
        groups.append({"name": "Dashboards", "icon": "bi-bar-chart-line-fill",
                        "tint": "#0891B2", "links": [
                            {"label": "Indicadores", "icon": "bi-speedometer2",
                             "url": url_for("dashboard.indicadores"),
                             "desc": "Dashboard gerencial de KPIs"}
                        ]})

    seg_items = []
    if u.tiene_permiso("bi_seguimiento"):
        seg_items.append({"label": "Archivo de Seguimiento", "icon": "bi-folder2-open",
                           "url": url_for("coordinador.bi_seguimiento"),
                           "desc": "Informe operacional de seguimiento (Power BI)"})
    if u.tiene_permiso("preoperacionales") or u.tiene_permiso("preoperacionales_dashboard"):
        seg_items.append({"label": "Preoperacionales", "icon": "bi-clipboard-check-fill",
                           "url": url_for("coordinador.preoperacionales"),
                           "desc": "Cumplimiento, estado de vehículos y placas"})
    if u.tiene_permiso("semaforo"):
        seg_items.append({"label": "Semáforo (calificar)", "icon": "bi-stoplights-fill",
                           "url": url_for("coordinador.semaforo_dashboard"),
                           "desc": "Registra calificaciones de actividades por contrato"})
    if u.tiene_permiso("semaforo_dashboard"):
        seg_items.append({"label": "Semáforo Dashboard", "icon": "bi-bar-chart-steps",
                           "url": url_for("coordinador.semaforo_dashboard"),
                           "desc": "Visualiza el estado del semáforo sin calificar"})
    if seg_items:
        groups.append({"name": "Seguimiento y Calidad", "icon": "bi-clipboard2-data",
                        "tint": "#16A34A", "links": seg_items})

    if u.tiene_permiso("gps"):
        groups.append({"name": "GPS", "icon": "bi-geo-alt-fill", "tint": "#DC2626",
                        "links": [{"label": "Rastrear", "icon": "bi-map",
                                   "url": "https://plataforma.sistemagps.online/ui/map/objects",
                                   "ext": True, "desc": "Mapa de vehículos en vivo"}]})

    if not groups:
        groups.append({"name": "Sin módulos asignados", "icon": "bi-info-circle",
                        "tint": "#6B7280", "links": [
                            {"label": "Contacte al administrador", "icon": "bi-person-lock",
                             "url": "#", "desc": "Su cuenta no tiene módulos habilitados aún"}
                        ]})

    return render_template(
        "portal/home.html",
        page_title="Inicio",
        page_desc="Panel de acceso según permisos asignados",
        intro_title=f"Hola, {u.nombre_completo}",
        intro_sub="Tus módulos disponibles",
        groups=groups,
        home_endpoint=None,
    )

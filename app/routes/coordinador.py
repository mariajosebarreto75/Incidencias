
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
        # "2.457.051" → quitar puntos de miles → float
        return float(str(valor).strip().replace(".", "").replace(",", "."))
    except Exception:
        return None


def formatear_coordenada(valor, posicion_coma):
    """
    Normaliza coordenadas al formato con coma decimal.
    Casos:
      - Ya tiene coma            → devuelve tal cual
      - Tiene punto real decimal → reemplaza punto por coma  (-74.638 → -74,638)
      - Float .0 de pandas       → trata como entero         (-4493839.0 → -44,93839)
      - Entero puro              → inserta coma en posición   36364567 → 3,6364567
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
            # Es X.0 o X.000 → tratar como entero
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
    """Sincroniza el plan del día desde GPS Monitor para la fecha solicitada."""
    from app.services.sincronizar_plan import sincronizar_plan
    datos = request.get_json(silent=True) or {}
    from_date = datos.get("desde") or datos.get("fecha") or None
    to_date   = datos.get("hasta") or datos.get("fecha_fin") or from_date
    resultado = sincronizar_plan(from_date, to_date)
    if "error" in resultado:
        return jsonify({"ok": False, "error": resultado["error"]}), 500
    return jsonify({"ok": True, **resultado})


@coordinador.route(
    "/coordinador/distribucion-operativa",
    methods=["GET", "POST"]
)
@login_required
def distribucion_operativa():

    if request.method == "POST":

        archivo = request.files.get(
            "archivo"
        )

        if not archivo:

            flash(
                "Debe seleccionar un archivo",
                "danger"
            )

            return redirect(
                request.url
            )

        # ==========================
        # LEER EXCEL EN MEMORIA
        # (sin guardar en disco)
        # ==========================

        import pandas as pd
        import io
        df = pd.read_excel(
            io.BytesIO(archivo.read())
        )

        df.columns = (
            df.columns.str.strip()
        )

        print(df.dtypes)

        print("\n=========================")
        print("COLUMNAS ENCONTRADAS")
        print("=========================")
        print(df.columns.tolist())

        print("\n=========================")
        print("PRIMERAS FILAS")
        print("=========================")
        print(df.head())

        try:

            for idx, row in df.iterrows():

                # ==========================
                # VARIABLES PRINCIPALES
                # ==========================

                contrato_raw = str(row["contrato"]).strip()
                # Resolver: acepta nombre completo o código corto
                _ct = Contrato.query.filter(
                    (Contrato.contrato == contrato_raw) |
                    (Contrato.codigo   == contrato_raw)
                ).first()
                if not _ct:
                    raise Exception(
                        f"Contrato no encontrado: '{contrato_raw}'. "
                        f"Usa el nombre completo o el código del contrato."
                    )
                contrato = _ct.contrato

                recurso = str(
                    row["recurso"]
                ).strip()

                if (
                    pd.isna(row["recurso"])
                    or recurso == ""
                    or recurso.lower() == "nan"
                ):

                    raise Exception(
                        "Existen registros sin recurso."
                    )

                placa = str(
                    row["placa"]
                ).strip().upper()
                if not re.match(
                    r"^[A-Z]{3}[A-Z0-9]{2,3}$",
                    placa
                ):

                    raise Exception(
                        f"Placa inválida: {placa}"
                    )

                actividad = (
                    ""
                    if pd.isna(row["tipo_actividad"])
                    else str(row["tipo_actividad"]).strip()
                )

                tipo_cuadrilla = str(
                    row["tipo_cuadrilla"]
                ).strip()

                # ==========================
                # BUSCAR META AUTOMATICA
                # ==========================

                meta_operativa = (
                    MetaOperativa.query.filter(
                        MetaOperativa.contrato == contrato,
                        db.func.lower(db.func.trim(MetaOperativa.Tipo_cuadrilla))
                        == tipo_cuadrilla.lower().strip()
                    ).first()
                )

                meta_calculada = None

                if meta_operativa:

                    meta_calculada = (
                        meta_operativa.Meta_Produccion
                    )

                print(
                    contrato,
                    tipo_cuadrilla,
                    meta_calculada
                )

                # ==========================
                # ACTIVIDADES
                # ==========================

                if actividad:

                    existe_actividad = (
                        Actividad.query.filter_by(
                            actividad=actividad,
                            contrato=contrato
                        ).first()
                    )

                    if not existe_actividad:

                        db.session.add(
                            Actividad(
                                actividad=actividad,
                                contrato=contrato
                            )
                        )
                # ==========================
                # VALIDAR FECHA
                # ==========================

                fecha = pd.to_datetime(
                    row["fecha"]
                ).date()

                hoy   = datetime.now().date()
                ayer  = hoy - timedelta(days=1)
                manana = hoy + timedelta(days=1)

                if fecha < ayer:

                    raise Exception(
                        f"La fecha {fecha} no puede ser anterior a ayer."
                    )

                if fecha > manana:

                    raise Exception(
                        f"La fecha {fecha} solo puede ser ayer, hoy o mañana."
                    )

                # ==========================
                # ORDEN DE TRABAJO
                # ==========================

                _ot_raw = row.get("orden_trabajo") if "orden_trabajo" in df.columns else None
                orden_trabajo = (
                    None
                    if _ot_raw is None or pd.isna(_ot_raw)
                       or str(_ot_raw).strip() in ("", "NA", "nan")
                    else str(_ot_raw).strip()
                )


                # ==========================
                # COORDENADAS
                # ==========================

                latitud = formatear_coordenada(
                    ""
                    if pd.isna(row["latitud"])
                    else str(row["latitud"]),
                    1
                )

                longitud = formatear_coordenada(
                    ""
                    if pd.isna(row["longitud"])
                    else str(row["longitud"]),
                    2
                )


                # ==========================
                # DURACIÓN (solo minutos)
                # ==========================

                duracion_raw = (
                    ""
                    if pd.isna(row["duracion_actividad"])
                    else str(row["duracion_actividad"]).strip()
                )

                if duracion_raw:

                    try:
                        duracion_int = int(float(duracion_raw))
                        if duracion_int <= 0:
                            raise ValueError()
                        duracion_actividad = str(duracion_int)
                    except (ValueError, TypeError):
                        raise Exception(
                            f"Fila {idx + 2}: duración inválida '{duracion_raw}'. "
                            f"Debe ser un número entero de minutos "
                            f"(ej: 60 para 1 hora, 90 para 1 hora 30 min)."
                        )

                else:
                    duracion_actividad = ""

                # ==========================
                # CEDULA 1 — validar persona
                # ==========================

                cedula_1_raw = (
                    ""
                    if pd.isna(row["cedula_1"])
                    else str(int(row["cedula_1"]))
                )

                if cedula_1_raw:

                    persona_c1 = Persona.query.filter_by(
                        Documento=cedula_1_raw
                    ).first()

                    if not persona_c1:
                        raise Exception(
                            f"Fila {idx + 2}: la cédula '{cedula_1_raw}' "
                            f"no está registrada en la tabla de personas. "
                            f"Créela primero antes de importar."
                        )

                # ==========================
                # DISTRIBUCION OPERATIVA
                # ==========================
                print(
                    "LATITUD:",
                    latitud
                )

                print(
                    "LONGITUD:",
                    longitud
                )
                sede_excel = ""
                if "sede" in df.columns and not pd.isna(row.get("sede", None)):
                    sede_excel = str(row["sede"]).strip()

                nuevo = DistribucionOperativa(

                    fecha=fecha,

                    contrato=contrato,

                    sede=sede_excel or None,

                    recurso=recurso,

                    placa=placa,

                    orden_trabajo=orden_trabajo,

                    tipo_actividad=actividad,

                    tipo_cuadrilla=tipo_cuadrilla,

                    cedula_1=cedula_1_raw,

                    cedula_2=(
                        ""
                        if pd.isna(row["cedula_2"])
                        else str(
                            int(row["cedula_2"])
                        )
                    ),

                    cedula_3=(
                        ""
                        if pd.isna(row["cedula_3"])
                        else str(
                            int(row["cedula_3"])
                        )
                    ),

                    cedula_4=(
                        ""
                        if pd.isna(row["cedula_4"])
                        else str(
                            int(row["cedula_4"])
                        )
                    ),

                    cedula_5=(
                        ""
                        if pd.isna(row["cedula_5"])
                        else str(
                            int(row["cedula_5"])
                        )
                    ),

                    numero_celular=(
                        ""
                        if pd.isna(row["numero_celular"])
                        else str(
                            int(row["numero_celular"])
                        )
                    ),

                    latitud=latitud,

                    longitud=longitud,

                    duracion_actividad=duracion_actividad,

                    observacion=(
                        ""
                        if pd.isna(
                            row["observacion"]
                        )
                        else str(
                            row["observacion"]
                        ).strip()
                    ),

                    meta=meta_calculada
                )
                

                db.session.add(
                    nuevo
                )

                # ==========================
                # RECURSO CONTRATO
                # ==========================

                existe_recurso = (
                    RecursoContrato.query.filter_by(
                        recurso=recurso,
                        contrato=contrato
                    ).first()
                )

                if not existe_recurso:

                    db.session.add(
                        RecursoContrato(
                            recurso=recurso,
                            contrato=contrato
                        )
                    )

                # ==========================
                # PLACA CONTRATO
                # ==========================

                existe_placa = (
                    PlacaContrato.query.filter_by(
                        placa=placa,
                        contrato=contrato
                    ).first()
                )

                if not existe_placa:

                    db.session.add(
                        PlacaContrato(
                            placa=placa,
                            contrato=contrato
                        )
                    )

            db.session.commit()

            print(
                f"SE GUARDARON {len(df)} REGISTROS"
            )

            flash(
                f"{len(df)} registros guardados correctamente 🚀",
                "success"
            )

        except Exception as e:

            db.session.rollback()

            print(
                "ERROR AL GUARDAR:"
            )

            print(e)

            flash(
                str(e),
                "danger"
            )

        return redirect(
            request.url
        )
    # ==========================
    # CONTRATOS DEL COORDINADOR
    # ==========================

    _uc2 = UserContrato.query.filter_by(user_id=current_user.id).all()
    if _uc2:
        _nombres_uc2 = [uc.contrato for uc in _uc2]
        contratos_usuario = Contrato.query.filter(
            Contrato.contrato.in_(_nombres_uc2), Contrato.activo == True
        ).all()
        lista_contratos = [c.contrato for c in contratos_usuario]
    else:
        contratos_usuario = Contrato.query.filter_by(
            coordinador=current_user.nombre_completo, activo=True
        ).all()
        lista_contratos = [c.contrato for c in contratos_usuario]
    # ==========================
    # CUADRILLAS
    # ==========================

    cuadrillas = (
        db.session.query(
            MetaOperativa.Tipo_cuadrilla
        )
        .distinct()
        .all()
    )

    lista_cuadrillas = [

        c[0]

        for c in cuadrillas

    ]

    # ==========================
    # CONSULTAR REGISTROS
    # ==========================

    q = DistribucionOperativa.query
    if lista_contratos:
        q = q.filter(DistribucionOperativa.contrato.in_(lista_contratos))
    registros = q.order_by(DistribucionOperativa.id.desc()).limit(200).all()

    # Lookup en batch de personas por cedula_1
    cedulas_1 = [
        r.cedula_1
        for r in registros
        if r.cedula_1
    ]

    personas_map = {
        p.Documento: p
        for p in Persona.query.filter(
            Persona.Documento.in_(cedulas_1)
        ).all()
    } if cedulas_1 else {}

    datos_tabla = []

    for r in registros:

        persona = personas_map.get(r.cedula_1)

        datos_tabla.append({

            "id": r.id,
            "fecha": str(r.fecha),
            "contrato": r.contrato,
            "recurso": r.recurso,
            "placa": r.placa,
            "orden_trabajo": r.orden_trabajo,
            "tipo_actividad": r.tipo_actividad,
            "tipo_cuadrilla": r.tipo_cuadrilla,
            "hora_salida_sede": (
                ""
                if r.hora_salida_sede is None
                else str(r.hora_salida_sede)
            ),
            "hora_llegada_sede": (
                ""
                if r.hora_llegada_sede is None
                else str(r.hora_llegada_sede)
            ),
            "cedula_1": r.cedula_1,
            "nombre_1": persona.Nombre if persona else "",
            "cargo_1":  persona.Cargo  if persona else "",
            "cedula_2": r.cedula_2,
            "cedula_3": r.cedula_3,
            "cedula_4": r.cedula_4,
            "cedula_5": r.cedula_5,
            "numero_celular": (
                ""
                if r.numero_celular is None
                else str(r.numero_celular)
            ),
            "latitud": r.latitud,
            "longitud": r.longitud,
            "duracion_actividad": r.duracion_actividad,
            "observacion": (
                ""
                if r.observacion is None
                else r.observacion
            ),
            "meta": (
                "{:,.0f}".format(r.meta)
                .replace(",", ".")
                if r.meta
                else ""
            )

        })

    return render_template(
        "coordinador/distribucion_operativa.html",

        datos_tabla=json.dumps(
            datos_tabla,
            ensure_ascii=False
        ),
        contratos=json.dumps(
            lista_contratos,
            ensure_ascii=False
        ),
        cuadrillas=json.dumps(
            lista_cuadrillas,
            ensure_ascii=False
        )
    )
# =====================================
# GUARDAR CAMBIOS TABULATOR
# =====================================

@coordinador.route(
    "/coordinador/guardar-distribucion",
    methods=["POST"]
)
@login_required
def guardar_distribucion():

    try:

        datos = request.get_json()

        filas_nuevas = datos.get(
            "filasNuevas",
            []
        )
        filas_editadas = datos.get(
            "filasEditadas",
            []
        )
        filas_eliminadas = datos.get(
            "filasEliminadas",
            []
        )
        print("\n===================")
        print("FILAS ELIMINADAS")
        print("===================")

        for fila in filas_eliminadas:

            print(fila)

        guardados = 0

        for fila in filas_nuevas:

            contrato = fila.get(
                "contrato"
            )

            recurso = fila.get(
                "recurso"
            )

            # ==========================
            # RECURSO OBLIGATORIO
            # ==========================

            if not recurso:

                return jsonify({

                    "success": False,

                    "mensaje":
                        "Debe ingresar un recurso."

                }), 400
            
            # ==========================
            # PLACA OBLIGATORIA Y VÁLIDA
            # ==========================

            placa = str(
                fila.get(
                    "placa",
                    ""
                )
            ).strip().upper()

            if not placa:

                return jsonify({

                    "success": False,

                    "mensaje":
                        "Debe ingresar una placa."

                }), 400

            if not re.match(
                r"^[A-Z]{3}[A-Z0-9]{2,3}$",
                placa
            ):

                return jsonify({

                    "success": False,

                    "mensaje":
                        f"Placa inválida: {placa}"

                }), 400

            # ==========================
            # VALIDACIONES
            # ==========================

            if not contrato:

                continue

            if not fila.get(
                "fecha"
            ):

                continue

            fecha_texto = fila.get(
                "fecha"
            )

            fecha = None

            try:

                fecha = datetime.strptime(
                    fecha_texto,
                    "%Y-%m-%d"
                ).date()

            except:

                try:

                    fecha = datetime.strptime(
                        fecha_texto,
                        "%d/%m/%Y"
                    ).date()

                except:

                    continue

            hoy   = datetime.now().date()
            ayer  = hoy - timedelta(days=1)
            manana = hoy + timedelta(days=1)

            if fecha < ayer:

                return jsonify({

                    "success": False,

                    "mensaje":
                        f"La fecha {fecha} no puede ser anterior a ayer."

                }), 400

            if fecha > manana:

                return jsonify({

                    "success": False,

                    "mensaje":
                        f"La fecha {fecha} solo puede ser ayer, hoy o mañana."

                }), 400

            # ==========================
            # ORDEN DE TRABAJO (opcional)
            # ==========================

            orden_trabajo = fila.get("orden_trabajo") or None

            # ==========================
            # NUEVO REGISTRO
            # ==========================

            nuevo = DistribucionOperativa(

                fecha=fecha,

                contrato=contrato,

                sede=(fila.get("sede") or "").strip() or None,

                recurso=recurso,

                placa=placa,

                orden_trabajo=fila.get(
                    "orden_trabajo"
                ),

                tipo_actividad=fila.get(
                    "tipo_actividad"
                ),

                tipo_cuadrilla=fila.get(
                    "tipo_cuadrilla"
                ),

                hora_salida_sede=parsear_hora(
                    fila.get("hora_salida_sede")
                ),

                hora_llegada_sede=parsear_hora(
                    fila.get("hora_llegada_sede")
                ),

                cedula_1=fila.get(
                    "cedula_1"
                ),

                cedula_2=fila.get(
                    "cedula_2"
                ),

                cedula_3=fila.get(
                    "cedula_3"
                ),

                cedula_4=fila.get(
                    "cedula_4"
                ),

                cedula_5=fila.get(
                    "cedula_5"
                ),

                numero_celular=fila.get(
                    "numero_celular"
                ),

                latitud=fila.get(
                    "latitud"
                ),

                longitud=fila.get(
                    "longitud"
                ),

                duracion_actividad=fila.get(
                    "duracion_actividad"
                ),

                observacion=fila.get(
                    "observacion"
                ),

                meta=parsear_meta(
                    fila.get("meta")
                )

            )

            db.session.add(
                nuevo
            )

            guardados += 1

        # ==========================
        #  ACTUALIZAR REGISTROS
        # ==========================
        print("\n===================")
        print("FILAS EDITADAS")
        print("===================")

        for fila in filas_editadas:

            print(fila)

            id_registro = fila.get("id")

            if not id_registro:

                print("SIN ID")
                continue

            registro = db.session.get(
                DistribucionOperativa,
                int(id_registro)
            )

            if not registro:

                continue
            
            orden_trabajo = fila.get("orden_trabajo") or None

            # ==========================
            # RECURSO OBLIGATORIO
            # ==========================

            if not fila.get("recurso"):

                return jsonify({

                    "success": False,

                    "mensaje":
                        "El recurso es obligatorio."

                }), 400
            
            # ==========================
            # PLACA OBLIGATORIA Y VÁLIDA
            # ==========================

            placa = str(
                fila.get(
                    "placa",
                    ""
                )
            ).strip().upper()

            if not placa:

                return jsonify({

                    "success": False,

                    "mensaje":
                        "Debe ingresar una placa."

                }), 400

            if not re.match(
                r"^[A-Z]{3}[A-Z0-9]{2,3}$",
                placa
            ):

                return jsonify({

                    "success": False,

                    "mensaje":
                        f"Placa inválida: {placa}"

                }), 400
            
            # ==========================
            # FECHA
            # ==========================

            if fila.get("fecha"):

                try:

                    fecha_editada = (
                        datetime.strptime(
                            fila.get("fecha"),
                            "%Y-%m-%d"
                        ).date()
                    )

                except:

                    try:

                        fecha_editada = (
                            datetime.strptime(
                                fila.get("fecha"),
                                "%d/%m/%Y"
                            ).date()
                        )

                    except:

                        return jsonify({

                            "success": False,

                            "mensaje":
                                "Formato de fecha inválido."

                        }), 400

                hoy   = datetime.now().date()
                ayer  = hoy - timedelta(days=1)
                manana = hoy + timedelta(days=1)

                if fecha_editada < ayer:

                    return jsonify({

                        "success": False,

                        "mensaje":
                            "La fecha no puede ser anterior a ayer."

                    }), 400

                if fecha_editada > manana:

                    return jsonify({

                        "success": False,

                        "mensaje":
                            "La fecha solo puede ser ayer, hoy o mañana."

                    }), 400

                registro.fecha = fecha_editada


            # ==========================
            # CAMPOS
            # ==========================

            registro.contrato = fila.get(
                "contrato"
            )

            registro.recurso = fila.get(
                "recurso"
            )

            registro.placa = placa

            registro.orden_trabajo = fila.get(
                "orden_trabajo"
            )

            registro.tipo_actividad = fila.get(
                "tipo_actividad"
            )

            registro.tipo_cuadrilla = fila.get(
                "tipo_cuadrilla"
            )

            registro.hora_salida_sede = parsear_hora(
                fila.get("hora_salida_sede")
            )

            registro.hora_llegada_sede = parsear_hora(
                fila.get("hora_llegada_sede")
            )

            registro.cedula_1 = fila.get(
                "cedula_1"
            )

            registro.cedula_2 = fila.get(
                "cedula_2"
            )

            registro.cedula_3 = fila.get(
                "cedula_3"
            )

            registro.cedula_4 = fila.get(
                "cedula_4"
            )

            registro.cedula_5 = fila.get(
                "cedula_5"
            )

            registro.numero_celular = fila.get(
                "numero_celular"
            )

            registro.latitud = (
                (fila.get("latitud") or "")
                .replace(".", ",")
            )

            registro.longitud = (
                (fila.get("longitud") or "")
                .replace(".", ",")
            )

            registro.duracion_actividad = fila.get(
                "duracion_actividad"
            )

            registro.observacion = fila.get(
                "observacion"
            )

            if fila.get("meta"):

                registro.meta = parsear_meta(
                    fila.get("meta")
                )

        # ==========================
        # ELIMINAR REGISTROS
        # ==========================
        
        print("\n===================")
        print("FILAS ELIMINADAS")
        print("===================")

        for fila in filas_eliminadas:

            id_registro = fila.get(
                "id"
            )

            if not id_registro:

                continue

            print(
                f"BUSCANDO ID {id_registro}"
            )

            registro = db.session.get(
                DistribucionOperativa,
                int(id_registro)
            )

            print(
                "REGISTRO:",
                registro
            )

            if registro:

                print(
                    f"ELIMINANDO {id_registro}"
                )

                db.session.delete(
                    registro
                )

            else:

                print(
                    f"NO EXISTE {id_registro}"
                )
        # ==========================
        # COMMIT
        # ==========================

        print(
            "\nREALIZANDO COMMIT..."
        )

        db.session.commit()
        print(
            "COMMIT EXITOSO"
        )


        return jsonify({

            "success": True,

                "mensaje": f"{guardados} registros nuevos guardados, "
                  f"{len(filas_editadas)} editados, " 
                  f"{len(filas_eliminadas)} eliminados."
        })

    except Exception as e:

        db.session.rollback()

        print(e)

        return jsonify({

            "success": False,

            "mensaje": str(e)

        }), 500
    
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
                "mensaje": f"La cédula {documento} ya está registrada."
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

    # Nombre completo del usuario que reportó
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
        "accion_a_tomar":     "Acción a tomar",
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
        # Notificar al NEO que reportó
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
        return jsonify({"success": False, "mensaje": "No se recibió archivo."}), 400

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
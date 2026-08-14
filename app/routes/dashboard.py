from flask import (
    Blueprint,
    render_template,
    request,
    url_for,
    abort
)

from flask_login import (
    login_required,
    current_user
)

from sqlalchemy import func, extract
from urllib.parse import urlencode
from datetime import date as _date

from app.extensions import db
from app.models.contrato import Contrato
from app.models.user_contrato import UserContrato
from app.models.reporte_operacional import ReporteOperacional


dashboard = Blueprint(
    "dashboard",
    __name__
)


# ======================
# DIRECTOR
# ======================

@dashboard.route(
    "/director"
)

@login_required
def director():

    return f"""

    Bienvenido Director:

    {current_user.nombre_completo}

    """


# =====================================
# DASHBOARD GERENCIAL (indicadores)
# =====================================

_TOP_N = 12

# Dimensiones filtrables por clic (estilo "cross-filter" de Power BI)
_DIMENSIONES = ("contrato", "recurso", "tipo", "accion", "conformidad")

_COLUMNA_POR_DIMENSION = {
    "contrato":     ReporteOperacional.contrato,
    "recurso":      ReporteOperacional.recurso,
    "tipo":         ReporteOperacional.tipo_incidencia,
    "accion":       ReporteOperacional.accion_a_tomar,
    "conformidad":  ReporteOperacional.conformidad_neo,
}


def _formato_dias_horas(total_horas):
    """Convierte un total de horas (float) a un texto compacto 'Xd Yh'/'Xh Ym'."""
    total_minutos = round((total_horas or 0) * 60)
    dias, resto = divmod(total_minutos, 24 * 60)
    horas, minutos = divmod(resto, 60)
    if dias > 0:
        return f"{dias}d {horas}h"
    return f"{horas}h {minutos}m"


@dashboard.route("/dashboard-gerencial")
@login_required
def indicadores():

    if not (current_user.rol.lower() in ("admin", "director") or current_user.acceso_dashboard):
        abort(403)

    # ---- Contratos visibles para este usuario (si no tiene asignados, ve todos) ----
    asignados = UserContrato.query.filter_by(user_id=current_user.id).all()
    contratos_restringidos = [uc.contrato for uc in asignados] if asignados else None

    if contratos_restringidos is not None:
        lista_contratos = sorted(contratos_restringidos)
    else:
        lista_contratos = [
            c.contrato for c in Contrato.query.order_by(Contrato.contrato).all()
        ]

    # Abreviación para mostrar en los gráficos: nombre corto > código > nombre completo.
    # Se ajusta desde Admin → Contratos (campos "Nombre corto" y "Código").
    abrev_por_contrato = {
        c.contrato: (c.nombre or c.codigo or c.contrato)
        for c in Contrato.query.all()
    }

    # ---- Filtros de mes/año ----
    anio_filtro = request.args.get("anio", "").strip()
    mes_filtro  = request.args.get("mes",  "").strip()
    anio_actual = _date.today().year
    lista_anios = list(range(anio_actual, anio_actual - 5, -1))
    meses_nombres = {
        "1": "Enero", "2": "Febrero", "3": "Marzo", "4": "Abril",
        "5": "Mayo", "6": "Junio", "7": "Julio", "8": "Agosto",
        "9": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre",
    }

    # ---- Filtros activos (cross-filter estilo Power BI) ----
    # "accion" admite selección múltiple (lista); el resto son valores únicos.
    activos = {}
    for dim in _DIMENSIONES:
        if dim == "accion":
            vals = [v.strip() for v in request.args.getlist("accion") if v.strip()]
            activos[dim] = vals
        else:
            valor = request.args.get(dim, "").strip()
            if dim == "contrato" and valor not in lista_contratos:
                valor = ""
            activos[dim] = valor

    def _params_base(excluir_dim=None, set_dim=None, set_val=None):
        """Construye el dict de parámetros de URL respetando multivalor de accion."""
        params = []
        for k, v in activos.items():
            if k == excluir_dim:
                continue
            if k == set_dim:
                continue
            if isinstance(v, list):
                for item in v:
                    params.append((k, item))
            elif v:
                params.append((k, v))
        if set_dim and set_val:
            if isinstance(set_val, list):
                for item in set_val:
                    params.append((set_dim, item))
            else:
                params.append((set_dim, set_val))
        if anio_filtro: params.append(("anio", anio_filtro))
        if mes_filtro:  params.append(("mes",  mes_filtro))
        return params

    def _url_toggle(dimension, valor):
        if dimension == "accion":
            lista = list(activos.get("accion") or [])
            if valor in lista:
                lista.remove(valor)
            else:
                lista.append(valor)
            p = _params_base(excluir_dim="accion", set_dim="accion", set_val=lista)
        else:
            nuevo_val = "" if activos.get(dimension) == valor else valor
            p = _params_base(excluir_dim=dimension)
            if nuevo_val:
                p.append((dimension, nuevo_val))
        base = url_for("dashboard.indicadores")
        return base + ("?" + urlencode(p) if p else "")

    def _url_quitar(dimension):
        p = _params_base(excluir_dim=dimension)
        base = url_for("dashboard.indicadores")
        return base + ("?" + urlencode(p) if p else "")

    def _filtros_sql(excluir=None):
        filtros = []
        if contratos_restringidos is not None:
            filtros.append(ReporteOperacional.contrato.in_(contratos_restringidos))
        for dim, valor in activos.items():
            if dim == excluir:
                continue
            if isinstance(valor, list):
                if valor:
                    filtros.append(_COLUMNA_POR_DIMENSION[dim].in_(valor))
            elif valor:
                filtros.append(_COLUMNA_POR_DIMENSION[dim] == valor)
        if anio_filtro:
            try: filtros.append(extract("year",  ReporteOperacional.fecha_reporte) == int(anio_filtro))
            except ValueError: pass
        if mes_filtro:
            try: filtros.append(extract("month", ReporteOperacional.fecha_reporte) == int(mes_filtro))
            except ValueError: pass
        return filtros

    def _query(excluir=None):
        q = db.session.query(ReporteOperacional)
        for f in _filtros_sql(excluir):
            q = q.filter(f)
        return q

    def _contar(columna, excluir=None):
        q = db.session.query(columna, func.count(ReporteOperacional.id))
        for f in _filtros_sql(excluir):
            q = q.filter(f)
        return q.group_by(columna).all()

    def _serie(pares, dimension, etiquetas=None, label_vacio="Sin dato"):
        """pares: [(valor, cantidad), ...]. `etiquetas` opcional: valor -> texto a mostrar."""
        etiquetas = etiquetas or {}
        limpio = [(v, (etiquetas.get(v, v) if v else label_vacio), c) for v, c in pares]
        limpio.sort(key=lambda p: p[2], reverse=True)
        top = limpio[:_TOP_N]
        resto = limpio[_TOP_N:]
        filas = []
        for valor, etiqueta, cantidad in top:
            filas.append({
                "etiqueta": etiqueta,
                "cantidad": cantidad,
                "url": _url_toggle(dimension, valor) if valor else None,
                "activo": bool(valor) and activos.get(dimension) == valor,
            })
        if resto:
            filas.append({
                "etiqueta": "Otros", "cantidad": sum(c for _, _, c in resto),
                "url": None, "activo": False,
            })
        maximo = max((f["cantidad"] for f in filas), default=0)
        return {"datos": filas, "maximo": maximo}

    # ---- KPIs (aplican TODOS los filtros activos) ----
    total_reportes = _query().count()
    total_pendientes = _query().filter(ReporteOperacional.estado == "Abierto").count()
    total_conformes = _query().filter(ReporteOperacional.conformidad_neo == "Conforme").count()
    total_no_conformes = _query().filter(ReporteOperacional.conformidad_neo == "No conforme").count()
    total_cerrados = _query().filter(ReporteOperacional.estado == "Cerrado").count()

    suma_horas = (
        db.session.query(func.sum(ReporteOperacional.horas_afectadas))
        .filter(*_filtros_sql()).scalar()
    ) or 0
    tiempo_desviacion_txt = _formato_dias_horas(suma_horas)

    suma_afectacion = (
        db.session.query(func.sum(ReporteOperacional.afectacion_economica))
        .filter(*_filtros_sql()).scalar()
    ) or 0

    # ---- Series (cada una excluye su propia dimensión para poder cambiar la selección) ----
    reportes_por_contrato = _serie(
        _contar(ReporteOperacional.contrato, excluir="contrato"), "contrato", abrev_por_contrato
    )
    reportes_por_recurso = _serie(_contar(ReporteOperacional.recurso, excluir="recurso"), "recurso")
    reportes_por_tipo = _serie(_contar(ReporteOperacional.tipo_incidencia, excluir="tipo"), "tipo")
    reportes_por_accion = _serie(
        _contar(ReporteOperacional.accion_a_tomar, excluir="accion"), "accion",
        label_vacio="Sin Respuesta"
    )

    # Afectación económica por tipo de incidencia
    afect_por_tipo_raw = (
        db.session.query(ReporteOperacional.tipo_incidencia,
                         func.sum(ReporteOperacional.afectacion_economica))
        .filter(*_filtros_sql(excluir="tipo"))
        .group_by(ReporteOperacional.tipo_incidencia).all()
    )
    afect_por_tipo = {(t or ""): round(a or 0) for t, a in afect_por_tipo_raw}

    # Listas de valores para los filtros desplegables
    lista_tipos = sorted(set(
        r[0] for r in db.session.query(ReporteOperacional.tipo_incidencia).distinct().all()
        if r[0]
    ))
    lista_acciones = sorted(set(
        r[0] for r in db.session.query(ReporteOperacional.accion_a_tomar).distinct().all()
        if r[0]
    ))
    lista_conformidades = ["Conforme", "No conforme"]

    # Horas afectadas y afectación económica por contrato
    horas_por_contrato_raw = (
        db.session.query(ReporteOperacional.contrato,
                         func.sum(ReporteOperacional.horas_afectadas),
                         func.sum(ReporteOperacional.afectacion_economica))
        .filter(*_filtros_sql(excluir="contrato"))
        .group_by(ReporteOperacional.contrato).all()
    )
    horas_por_contrato = []
    for contrato, hrs, afect in sorted(horas_por_contrato_raw, key=lambda x: -(x[1] or 0)):
        horas_por_contrato.append({
            "etiqueta": abrev_por_contrato.get(contrato, contrato) if contrato else "Sin dato",
            "horas": round(hrs or 0, 1),
            "afectacion": round(afect or 0),
            "url": _url_toggle("contrato", contrato) if contrato else None,
            "activo": bool(contrato) and activos.get("contrato") == contrato,
        })
    max_horas = max((r["horas"] for r in horas_por_contrato), default=1) or 1

    pendientes_por_contrato = _serie(
        db.session.query(ReporteOperacional.contrato, func.count(ReporteOperacional.id))
        .filter(ReporteOperacional.estado == "Abierto")
        .filter(*_filtros_sql(excluir="contrato"))
        .group_by(ReporteOperacional.contrato)
        .all(),
        "contrato", abrev_por_contrato
    )

    # ---- % de respuesta por contrato (excluye el filtro de contrato) ----
    filtros_sin_contrato = _filtros_sql(excluir="contrato")
    total_por_contrato = dict(
        db.session.query(ReporteOperacional.contrato, func.count(ReporteOperacional.id))
        .filter(*filtros_sin_contrato).group_by(ReporteOperacional.contrato).all()
    )
    respondido_por_contrato = dict(
        db.session.query(ReporteOperacional.contrato, func.count(ReporteOperacional.id))
        .filter(ReporteOperacional.estado != "Abierto")
        .filter(*filtros_sin_contrato)
        .group_by(ReporteOperacional.contrato)
        .all()
    )
    pct_respuesta_datos = []
    for contrato, total in total_por_contrato.items():
        respondidos = respondido_por_contrato.get(contrato, 0)
        pct = round((respondidos / total * 100), 1) if total else 0
        pct_respuesta_datos.append({
            "etiqueta": abrev_por_contrato.get(contrato, contrato) if contrato else "Sin dato",
            "valor": pct,
            "url": _url_toggle("contrato", contrato) if contrato else None,
            "activo": bool(contrato) and activos.get("contrato") == contrato,
        })
    pct_respuesta_datos.sort(key=lambda p: p["valor"], reverse=True)
    pct_respuesta_por_contrato = {"datos": pct_respuesta_datos}

    # ---- % Conformidad NEO (torta — excluye su propio filtro) ----
    filtros_sin_conf = _filtros_sql(excluir="conformidad")
    conf_conformes = (
        db.session.query(func.count(ReporteOperacional.id))
        .filter(ReporteOperacional.conformidad_neo == "Conforme")
        .filter(*filtros_sin_conf).scalar()
    ) or 0
    conf_no_conformes = (
        db.session.query(func.count(ReporteOperacional.id))
        .filter(ReporteOperacional.conformidad_neo == "No conforme")
        .filter(*filtros_sin_conf).scalar()
    ) or 0
    total_calificados = conf_conformes + conf_no_conformes
    pct_conforme = round(conf_conformes / total_calificados * 100, 1) if total_calificados else 0
    pct_no_conforme = round(100 - pct_conforme, 1) if total_calificados else 0
    conformidad_pie = {
        "pct_conforme": pct_conforme,
        "pct_no_conforme": pct_no_conforme,
        "grados_conforme": round(pct_conforme * 3.6, 1),
        "total_conformes": conf_conformes,
        "total_no_conformes": conf_no_conformes,
        "url_conforme": _url_toggle("conformidad", "Conforme"),
        "url_no_conforme": _url_toggle("conformidad", "No conforme"),
        "activo_conforme": activos.get("conformidad") == "Conforme",
        "activo_no_conforme": activos.get("conformidad") == "No conforme",
    }

    # ---- Reportes por día (últimos 30 días con datos; aplica todos los filtros) ----
    por_dia_raw = (
        db.session.query(ReporteOperacional.fecha_reporte, func.count(ReporteOperacional.id))
        .filter(*_filtros_sql())
        .group_by(ReporteOperacional.fecha_reporte)
        .order_by(ReporteOperacional.fecha_reporte)
        .all()
    )[-30:]
    maximo_dia = max((c for _, c in por_dia_raw), default=0)
    reportes_por_dia = {
        "datos": [(f.strftime("%d/%m") if f else "Sin fecha", c) for f, c in por_dia_raw],
        "maximo": maximo_dia,
    }

    # ---- Chips de filtros activos ----
    etiquetas_dimension = {
        "contrato": "Contrato", "recurso": "Recurso", "tipo": "Tipo de incidencia",
        "accion": "Acción a tomar", "conformidad": "Conformidad NEO",
    }
    filtros_activos = []
    for dim, valor in activos.items():
        if isinstance(valor, list):
            for v in valor:
                filtros_activos.append({
                    "dimension": etiquetas_dimension[dim],
                    "texto": v,
                    "url_quitar": _url_toggle(dim, v),
                })
        elif valor:
            texto = abrev_por_contrato.get(valor, valor) if dim == "contrato" else valor
            filtros_activos.append({
                "dimension": etiquetas_dimension[dim],
                "texto": texto,
                "url_quitar": _url_quitar(dim),
            })

    # Nombre completo + rol para el encabezado / link de "volver"
    rol = current_user.rol.lower()
    home_por_rol = {
        "neo":         "neo.home_neo",
        "coordinador": "coordinador.dashboard_coordinador",
        "admin":       "admin_bp.dashboard",
        "director":    "dashboard.director",
    }

    return render_template(
        "dashboard/indicadores.html",
        lista_contratos=lista_contratos,
        abrev_por_contrato=abrev_por_contrato,
        contrato_filtro=activos["contrato"],
        filtros_activos=filtros_activos,
        url_limpiar_todo=url_for("dashboard.indicadores"),
        anio_filtro=anio_filtro,
        mes_filtro=mes_filtro,
        lista_anios=lista_anios,
        meses_nombres=meses_nombres,
        kpis={
            "total_reportes":       total_reportes,
            "total_pendientes":     total_pendientes,
            "total_conformes":      total_conformes,
            "total_no_conformes":   total_no_conformes,
            "total_cerrados":       total_cerrados,
            "tiempo_desviacion":    tiempo_desviacion_txt,
            "afectacion_economica": suma_afectacion,
            "horas_afectadas":      round(suma_horas, 1),
        },
        reportes_por_contrato=reportes_por_contrato,
        pendientes_por_contrato=pendientes_por_contrato,
        reportes_por_recurso=reportes_por_recurso,
        reportes_por_tipo=reportes_por_tipo,
        reportes_por_accion=reportes_por_accion,
        pct_respuesta_por_contrato=pct_respuesta_por_contrato,
        conformidad_pie=conformidad_pie,
        reportes_por_dia=reportes_por_dia,
        horas_por_contrato=horas_por_contrato,
        max_horas=max_horas,
        afect_por_tipo=afect_por_tipo,
        lista_tipos=lista_tipos,
        lista_acciones=lista_acciones,
        lista_conformidades=lista_conformidades,
        activos=activos,
        home_endpoint=home_por_rol.get(rol),
    )

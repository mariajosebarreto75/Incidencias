"""
Script one-shot: recalcula afectacion_economica de todos los reportes operacionales
usando la formula correcta (meta / 7.33) * horas_afectadas, la misma que usa el
formulario de creacion en app/static/js/neo/PanelNeo.js y el backend (app/routes/neo.py).

Ademas de corregir el resultado de la formula, repara el origen del dato 'meta'
en dos casos detectados en el primer dry-run:

  1. Reportes sin 'meta' guardada: se busca el valor oficial en la tabla
     metas_operativas por (contrato, tipo_cuadrilla) -- misma fuente de verdad
     que ahora usa el backend al crear/editar reportes. Si no hay match en el
     catalogo, el reporte queda para revision manual (no se toca).

  2. Reportes con 'meta' implausiblemente pequena (ej. 452.499 en vez de
     452499): esto viene de un bug ya corregido en _parsear_float, que
     interpretaba el punto de miles como decimal cuando el valor no traia
     coma. Se corrige multiplicando por 1000 (se confirmo contra el propio
     dataset: 452.499 * 1000 = 452499.0, un valor de meta real que aparece
     en muchos otros reportes del mismo contrato/cuadrilla).

El detalle completo (linea por linea, con meta antes/despues) se escribe a un
CSV junto al script; en la consola solo se muestra un resumen y ejemplos.

Uso:
    python scripts/recalcular_afectacion_economica.py --dry-run   (solo muestra el diagnostico)
    python scripts/recalcular_afectacion_economica.py             (aplica los cambios)
"""
import csv
import sys, os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run import create_app
from app.extensions import db
from app.models.reporte_operacional import ReporteOperacional
from app.models.meta_operativa import MetaOperativa

HORAS_DIA_ESTANDAR = 7.33
META_MIN_PLAUSIBLE = 1000  # metas reales observadas son > 100.000; por debajo de esto, se asume error de captura
DRY_RUN = "--dry-run" in sys.argv
MAX_EJEMPLOS_CONSOLA = 15


def recalc(r, meta):
    return round((meta / HORAS_DIA_ESTANDAR) * r.horas_afectadas, 2)


app = create_app()
with app.app_context():
    metas_map = {
        (m.contrato.strip().lower(), m.Tipo_cuadrilla.strip().lower()): m.Meta_Produccion
        for m in MetaOperativa.query.all()
    }

    candidatos = ReporteOperacional.query.filter(
        ReporteOperacional.horas_afectadas.isnot(None)
    ).order_by(ReporteOperacional.id).all()

    filas_csv = []
    corregidos = []          # meta ya era plausible, solo cambia afectacion
    meta_recuperada = []     # meta era None, se recuperó del catálogo
    meta_corregida = []      # meta estaba /1000 por el bug viejo, se corrige *1000
    sin_meta_manual = []     # meta None y sin match en catálogo -> revisión manual
    sin_cambio = 0

    for r in candidatos:
        clave = ((r.contrato or "").strip().lower(), (r.tipo_cuadrilla or "").strip().lower())

        if not r.meta:
            meta_catalogo = metas_map.get(clave)
            if meta_catalogo:
                nuevo_af = recalc(r, meta_catalogo)
                meta_recuperada.append((r, r.afectacion_economica, nuevo_af, None, meta_catalogo))
                r.meta = meta_catalogo
                r.afectacion_economica = nuevo_af
            elif r.afectacion_economica:
                sin_meta_manual.append(r)
            continue

        if r.meta < META_MIN_PLAUSIBLE:
            meta_fija = round(r.meta * 1000, 2)
            nuevo_af = recalc(r, meta_fija)
            meta_corregida.append((r, r.afectacion_economica, nuevo_af, r.meta, meta_fija))
            r.meta = meta_fija
            r.afectacion_economica = nuevo_af
            continue

        nuevo_valor = recalc(r, r.meta)
        actual = round(r.afectacion_economica or 0, 2)
        if abs(nuevo_valor - actual) < 0.01:
            sin_cambio += 1
            continue
        corregidos.append((r, actual, nuevo_valor))
        r.afectacion_economica = nuevo_valor

    def resumen(nombre, lista):
        print(f"{nombre}: {len(lista)}")

    print(f"Reportes con horas_afectadas: {len(candidatos)}")
    print(f"Ya correctos (sin cambio):    {sin_cambio}")
    resumen("A corregir (meta ya era plausible)", corregidos)
    resumen("Meta recuperada del catálogo (antes None)", meta_recuperada)
    resumen("Meta corregida x1000 (bug de parseo viejo)", meta_corregida)
    resumen("Sin meta y sin match en catálogo (revisión manual)", sin_meta_manual)

    def imprimir_ejemplos(titulo, lista, fmt):
        if not lista:
            return
        print(f"\n{titulo} -- primeros {min(MAX_EJEMPLOS_CONSOLA, len(lista))} (completo en el CSV):")
        for item in lista[:MAX_EJEMPLOS_CONSOLA]:
            print("  " + fmt(item))

    imprimir_ejemplos(
        "A corregir", corregidos,
        lambda t: f"#{t[0].id}: afectacion {t[1]:,.2f} -> {t[2]:,.2f} (meta={t[0].meta})"
    )
    imprimir_ejemplos(
        "Meta recuperada del catálogo", meta_recuperada,
        lambda t: f"#{t[0].id}: meta None -> {t[4]}, afectacion {t[1] or 0:,.2f} -> {t[2]:,.2f}"
    )
    imprimir_ejemplos(
        "Meta corregida x1000", meta_corregida,
        lambda t: f"#{t[0].id}: meta {t[3]} -> {t[4]}, afectacion {t[1] or 0:,.2f} -> {t[2]:,.2f}"
    )
    imprimir_ejemplos(
        "Sin meta, sin catálogo", sin_meta_manual,
        lambda r: f"#{r.id}: contrato='{r.contrato}', tipo_cuadrilla='{r.tipo_cuadrilla}', afectacion_actual={r.afectacion_economica}"
    )

    if corregidos or meta_recuperada or meta_corregida:
        suma_antes = (
            sum(a for _, a, _ in corregidos)
            + sum((a or 0) for _, a, _, _, _ in meta_recuperada)
            + sum((a or 0) for _, a, _, _, _ in meta_corregida)
        )
        suma_despues = (
            sum(n for _, _, n in corregidos)
            + sum(n for _, _, n, _, _ in meta_recuperada)
            + sum(n for _, _, n, _, _ in meta_corregida)
        )
        print(f"\nSuma afectacion total (todo lo corregido) antes:  ${suma_antes:,.2f}")
        print(f"Suma afectacion total (todo lo corregido) despues: ${suma_despues:,.2f}")

    # CSV con el detalle completo de todas las categorias
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"recalculo_afectacion_{ts}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["categoria", "id", "contrato", "tipo_cuadrilla", "meta_antes", "meta_despues",
                     "horas_afectadas", "impacto", "afectacion_antes", "afectacion_despues"])
        for r, actual, nuevo in corregidos:
            w.writerow(["a_corregir", r.id, r.contrato, r.tipo_cuadrilla, r.meta, r.meta,
                        r.horas_afectadas, r.impacto, actual, nuevo])
        for r, actual, nuevo, meta_antes, meta_despues in meta_recuperada:
            w.writerow(["meta_recuperada_catalogo", r.id, r.contrato, r.tipo_cuadrilla, meta_antes, meta_despues,
                        r.horas_afectadas, r.impacto, actual, nuevo])
        for r, actual, nuevo, meta_antes, meta_despues in meta_corregida:
            w.writerow(["meta_corregida_x1000", r.id, r.contrato, r.tipo_cuadrilla, meta_antes, meta_despues,
                        r.horas_afectadas, r.impacto, actual, nuevo])
        for r in sin_meta_manual:
            w.writerow(["sin_meta_manual", r.id, r.contrato, r.tipo_cuadrilla, r.meta, "",
                        r.horas_afectadas, r.impacto, r.afectacion_economica, ""])
    print(f"\nDetalle completo escrito en: {csv_path}")

    if DRY_RUN:
        db.session.rollback()
        print("\n--dry-run: no se guardo ningun cambio.")
    else:
        db.session.commit()
        total_tocados = len(corregidos) + len(meta_recuperada) + len(meta_corregida)
        print(f"\nListo. {total_tocados} reportes actualizados.")

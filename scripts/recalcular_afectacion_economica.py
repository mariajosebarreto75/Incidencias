"""
Script one-shot: recalcula afectacion_economica de todos los reportes operacionales
usando la formula correcta (meta / 7.33) * horas_afectadas, la misma que usa el
formulario de creacion en app/static/js/neo/PanelNeo.js.

Corrige los reportes que quedaron con el valor viejo (tarifa fija por impacto)
por haber pasado por "editar reporte" o "actualizar cuadrilla" antes del fix.

No toca automaticamente los reportes sin 'meta' guardada, ni los que tienen una
'meta' implausiblemente pequena (probable error de captura, ej. 452.499 en vez
de 452499) -- esos quedan listados para revision manual.

El detalle completo (linea por linea) se escribe a un CSV junto al script;
en la consola solo se muestra un resumen y ejemplos.

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

HORAS_DIA_ESTANDAR = 7.33
META_MIN_PLAUSIBLE = 1000  # metas reales observadas son > 100.000; por debajo de esto, se asume error de captura
DRY_RUN = "--dry-run" in sys.argv
MAX_EJEMPLOS_CONSOLA = 15

app = create_app()
with app.app_context():
    candidatos = ReporteOperacional.query.filter(
        ReporteOperacional.horas_afectadas.isnot(None)
    ).order_by(ReporteOperacional.id).all()

    corregidos = []
    sin_meta = []
    meta_sospechosa = []
    sin_cambio = 0

    for r in candidatos:
        if not r.meta:
            if r.afectacion_economica:
                sin_meta.append(r)
            continue

        if r.meta < META_MIN_PLAUSIBLE:
            meta_sospechosa.append(r)
            continue

        nuevo_valor = round((r.meta / HORAS_DIA_ESTANDAR) * r.horas_afectadas, 2)
        actual = round(r.afectacion_economica or 0, 2)

        if abs(nuevo_valor - actual) < 0.01:
            sin_cambio += 1
            continue

        corregidos.append((r, actual, nuevo_valor))
        r.afectacion_economica = nuevo_valor

    print(f"Reportes con horas_afectadas:        {len(candidatos)}")
    print(f"Ya correctos (sin cambio):            {sin_cambio}")
    print(f"Sin 'meta' (no recalculable):         {len(sin_meta)}")
    print(f"Meta sospechosa < {META_MIN_PLAUSIBLE} (no tocado): {len(meta_sospechosa)}")
    print(f"A corregir:                           {len(corregidos)}")

    if sin_meta:
        print(f"\nSin 'meta' -- primeros {min(MAX_EJEMPLOS_CONSOLA, len(sin_meta))} (completo en el CSV):")
        for r in sin_meta[:MAX_EJEMPLOS_CONSOLA]:
            print(f"  #{r.id}: afectacion_actual={r.afectacion_economica}")

    if meta_sospechosa:
        print(f"\nMeta sospechosa -- primeros {min(MAX_EJEMPLOS_CONSOLA, len(meta_sospechosa))} (completo en el CSV):")
        for r in meta_sospechosa[:MAX_EJEMPLOS_CONSOLA]:
            print(f"  #{r.id}: meta={r.meta}, afectacion_actual={r.afectacion_economica}")

    if corregidos:
        suma_antes = sum(actual for _, actual, _ in corregidos)
        suma_despues = sum(nuevo for _, _, nuevo in corregidos)
        print(f"\nSuma afectacion (reportes a corregir) antes:  ${suma_antes:,.2f}")
        print(f"Suma afectacion (reportes a corregir) despues: ${suma_despues:,.2f}")
        print(f"\nA corregir -- primeros {min(MAX_EJEMPLOS_CONSOLA, len(corregidos))} (completo en el CSV):")
        for r, actual, nuevo in corregidos[:MAX_EJEMPLOS_CONSOLA]:
            print(f"  #{r.id}: {actual:,.2f} -> {nuevo:,.2f}  (meta={r.meta}, horas={r.horas_afectadas}, impacto={r.impacto})")

    # CSV con el detalle completo de las 3 categorias
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"recalculo_afectacion_{ts}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["categoria", "id", "meta", "horas_afectadas", "impacto", "afectacion_antes", "afectacion_despues"])
        for r, actual, nuevo in corregidos:
            w.writerow(["a_corregir", r.id, r.meta, r.horas_afectadas, r.impacto, actual, nuevo])
        for r in sin_meta:
            w.writerow(["sin_meta", r.id, r.meta, r.horas_afectadas, r.impacto, r.afectacion_economica, ""])
        for r in meta_sospechosa:
            w.writerow(["meta_sospechosa", r.id, r.meta, r.horas_afectadas, r.impacto, r.afectacion_economica, ""])
    print(f"\nDetalle completo escrito en: {csv_path}")

    if DRY_RUN:
        db.session.rollback()
        print("\n--dry-run: no se guardo ningun cambio.")
    else:
        db.session.commit()
        print(f"\nListo. {len(corregidos)} reportes actualizados.")

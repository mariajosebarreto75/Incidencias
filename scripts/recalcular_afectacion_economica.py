"""
Script one-shot: recalcula afectacion_economica de todos los reportes operacionales
usando la formula correcta (meta / 7.33) * horas_afectadas, la misma que usa el
formulario de creacion en app/static/js/neo/PanelNeo.js.

Corrige los reportes que quedaron con el valor viejo (tarifa fija por impacto)
por haber pasado por "editar reporte" o "actualizar cuadrilla" antes del fix.

Uso:
    python scripts/recalcular_afectacion_economica.py --dry-run   (solo muestra el diagnostico)
    python scripts/recalcular_afectacion_economica.py             (aplica los cambios)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run import create_app
from app.extensions import db
from app.models.reporte_operacional import ReporteOperacional

HORAS_DIA_ESTANDAR = 7.33
DRY_RUN = "--dry-run" in sys.argv

app = create_app()
with app.app_context():
    candidatos = ReporteOperacional.query.filter(
        ReporteOperacional.horas_afectadas.isnot(None)
    ).all()

    corregidos = []
    sin_meta = []
    sin_cambio = 0

    for r in candidatos:
        if not r.meta:
            if r.afectacion_economica:
                sin_meta.append(r)
            continue

        nuevo_valor = round((r.meta / HORAS_DIA_ESTANDAR) * r.horas_afectadas, 2)
        actual = round(r.afectacion_economica or 0, 2)

        if abs(nuevo_valor - actual) < 0.01:
            sin_cambio += 1
            continue

        corregidos.append((r, actual, nuevo_valor))
        r.afectacion_economica = nuevo_valor

    print(f"Reportes con horas_afectadas: {len(candidatos)}")
    print(f"Ya correctos (sin cambio):    {sin_cambio}")
    print(f"Sin 'meta' (no recalculable): {len(sin_meta)}")
    print(f"A corregir:                   {len(corregidos)}")

    if sin_meta:
        print("\nReportes con afectacion_economica pero sin meta (revisar manualmente):")
        for r in sin_meta:
            print(f"  #{r.id}: meta=None, afectacion_actual={r.afectacion_economica}")

    if corregidos:
        suma_antes = sum(actual for _, actual, _ in corregidos)
        suma_despues = sum(nuevo for _, _, nuevo in corregidos)
        print(f"\nSuma afectacion (reportes a corregir) antes:  ${suma_antes:,.2f}")
        print(f"Suma afectacion (reportes a corregir) despues: ${suma_despues:,.2f}")
        print("\nDetalle:")
        for r, actual, nuevo in corregidos:
            print(f"  #{r.id}: {actual:,.2f} -> {nuevo:,.2f}  (meta={r.meta}, horas={r.horas_afectadas}, impacto={r.impacto})")

    if DRY_RUN:
        db.session.rollback()
        print("\n--dry-run: no se guardo ningun cambio.")
    else:
        db.session.commit()
        print(f"\nListo. {len(corregidos)} reportes actualizados.")

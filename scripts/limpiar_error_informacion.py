"""
Script one-shot: pone en NULL duracion, horas_afectadas y afectacion_economica
en todos los reportes con tipo_incidencia = 'Error en la información' (cualquier variante).
Ejecutar: python scripts/limpiar_error_informacion.py
"""
import sys, os, unicodedata
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run import create_app
from app.extensions import db
from app.models.reporte_operacional import ReporteOperacional

def _norm(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower().strip()

TARGET = "error en la informacion"

app = create_app()
with app.app_context():
    todos = ReporteOperacional.query.filter(
        ReporteOperacional.tipo_incidencia.isnot(None)
    ).all()

    afectados = [r for r in todos if _norm(r.tipo_incidencia) == TARGET]
    print(f"Reportes 'Error en la información' encontrados: {len(afectados)}")

    suma_hrs_antes = sum(r.horas_afectadas or 0 for r in afectados)
    suma_afe_antes = sum(r.afectacion_economica or 0 for r in afectados)
    print(f"Horas afectadas que se van a borrar: {suma_hrs_antes:.2f}h")
    print(f"Afectación económica que se va a borrar: ${suma_afe_antes:,.0f}")

    for r in afectados:
        r.duracion           = None
        r.horas_afectadas    = None
        r.afectacion_economica = None

    db.session.commit()
    print(f"\nListo. {len(afectados)} reportes actualizados.")

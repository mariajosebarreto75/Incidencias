"""
Script de solo lectura: lista los reportes de 'Salida tardía' con recurso tipo SEDE
que no tienen meta, numero_recursos ni meta_promedio -- por eso no calculan
afectación económica (falta la información de entrada para la fórmula).

Uso:
    python scripts/listar_sede_sin_datos.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run import create_app
from app.models.reporte_operacional import ReporteOperacional

app = create_app()
with app.app_context():
    candidatos = ReporteOperacional.query.filter(
        ReporteOperacional.tipo_incidencia.ilike("%salida tard%"),
        ReporteOperacional.recurso.ilike("%sede%"),
    ).order_by(ReporteOperacional.id).all()

    sin_datos = [
        r for r in candidatos
        if not r.meta and not r.numero_recursos and not r.meta_promedio
    ]

    print(f"Reportes 'Salida tardía' con recurso SEDE: {len(candidatos)}")
    print(f"Sin meta / numero_recursos / meta_promedio: {len(sin_datos)}\n")

    for r in sin_datos:
        print(f"#{r.id}  fecha={r.fecha_reporte}  contrato='{r.contrato}'  recurso='{r.recurso}'  "
              f"duracion={r.duracion}  afectacion_actual={r.afectacion_economica}  "
              f"reportado_por={r.reportado_por}")

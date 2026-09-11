"""
Script one-shot: fusiona los cortes duplicados del rango 2026-08-18 → 2026-09-17
en el corte global (contrato_id IS NULL) y elimina los sobrantes.
Ejecutar: python scripts/merge_cortes.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import HeCorte, HoraExtra
from datetime import date

app = create_app()

with app.app_context():
    fi = date(2026, 8, 18)
    ff = date(2026, 9, 17)

    # Corte global (Todos)
    corte_global = HeCorte.query.filter(
        HeCorte.fecha_inicio == fi,
        HeCorte.fecha_fin    == ff,
        HeCorte.contrato_id  == None,
    ).first()

    if not corte_global:
        print("ERROR: no se encontró el corte global (Todos) para ese rango.")
        sys.exit(1)

    print(f"Corte global encontrado: id={corte_global.id} — {corte_global.nombre}")

    # Cortes sobrantes con el mismo rango y contrato_id específico
    sobrantes = HeCorte.query.filter(
        HeCorte.fecha_inicio == fi,
        HeCorte.fecha_fin    == ff,
        HeCorte.contrato_id  != None,
    ).all()

    if not sobrantes:
        print("No hay cortes sobrantes. Nada que hacer.")
        sys.exit(0)

    for c in sobrantes:
        n = HoraExtra.query.filter(HoraExtra.corte_id == c.id).update(
            {"corte_id": corte_global.id}, synchronize_session=False
        )
        print(f"  Corte id={c.id} '{c.nombre}' (contrato_id={c.contrato_id}): {n} registros reasignados al corte global.")
        db.session.delete(c)

    db.session.commit()
    print("Listo. Cortes sobrantes eliminados y registros fusionados en el corte global.")

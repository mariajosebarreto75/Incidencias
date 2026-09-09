"""
Migración: consolidar corte duplicado
--------------------------------------
Mueve horas del corte global "Corte 2026-08-18 → 2026-09-17" (contrato_id=NULL)
al corte "18 Agos - 17 Sep 2026" (contrato específico), evitando duplicados.
Llave de dedup: contrato_id + fecha_labor + cedula + id_concepto + horas_reportadas

Uso:
    flask shell < scripts/migrar_corte_duplicado.py
  o bien:
    cd c:/AppsNeo/incidencias_neo
    ..\env\Scripts\python -c "exec(open('scripts/migrar_corte_duplicado.py').read())"
    (con FLASK_APP configurado)
"""

from app.models.hora_extra import HoraExtra
from app.models.he_corte   import HeCorte
from app.extensions         import db

# ── 1. Localizar los dos cortes ──────────────────────────────────────────────
FECHA_INI = "2026-08-18"
FECHA_FIN = "2026-09-17"

from datetime import date
fi = date.fromisoformat(FECHA_INI)
ff = date.fromisoformat(FECHA_FIN)

cortes = HeCorte.query.filter_by(fecha_inicio=fi, fecha_fin=ff).all()

print(f"\n{'='*60}")
print(f"Cortes encontrados con rango {FECHA_INI} → {FECHA_FIN}:")
for c in cortes:
    n_horas = HoraExtra.query.filter_by(corte_id=c.id).count()
    print(f"  ID={c.id:4d}  contrato_id={str(c.contrato_id):6s}  nombre='{c.nombre}'  "
          f"horas={n_horas}")

if len(cortes) < 2:
    print("\n⚠  Solo hay un corte con este rango, no se requiere migración.")
    raise SystemExit(0)

# ── 2. Identificar corte destino (con contrato) y origen (global, sin contrato) ─
destino = next((c for c in cortes if c.contrato_id is not None), None)
origen  = next((c for c in cortes if c.contrato_id is None),     None)

if not destino or not origen:
    print("\n⚠  No se encontró un corte con contrato y uno sin contrato. Revisar manualmente.")
    raise SystemExit(1)

print(f"\n  DESTINO  → ID={destino.id} '{destino.nombre}' (contrato_id={destino.contrato_id})")
print(f"  ORIGEN   → ID={origen.id}  '{origen.nombre}'  (contrato_id=NULL)")

# ── 3. Construir set de llave única de horas en el DESTINO ───────────────────
horas_destino = HoraExtra.query.filter_by(corte_id=destino.id).all()
llaves_destino = {
    (h.contrato_id, str(h.fecha_labor), (h.cedula or "").strip(),
     (h.id_concepto or "").strip(), float(h.horas_reportadas or 0))
    for h in horas_destino
}
print(f"\n  Horas en DESTINO : {len(horas_destino)}")

# ── 4. Evaluar horas del ORIGEN ───────────────────────────────────────────────
horas_origen = HoraExtra.query.filter_by(corte_id=origen.id).all()
print(f"  Horas en ORIGEN  : {len(horas_origen)}")

mover    = []   # IDs a reasignar al destino
duplicar = []   # IDs que ya existen en destino (se dejan / quedan huérfanos)

for h in horas_origen:
    llave = (h.contrato_id, str(h.fecha_labor), (h.cedula or "").strip(),
             (h.id_concepto or "").strip(), float(h.horas_reportadas or 0))
    if llave in llaves_destino:
        duplicar.append(h.id)
    else:
        mover.append(h.id)

print(f"\n  Horas a MOVER al destino (únicas): {len(mover)}")
print(f"  Horas DUPLICADAS (ya existen)     : {len(duplicar)}")

if duplicar:
    print("\n  Registros duplicados (se van a dejar corte_id=NULL para no perderlos):")
    for hid in duplicar[:20]:
        h = HoraExtra.query.get(hid)
        print(f"    ID={hid} fecha={h.fecha_labor} ced={h.cedula} conc={h.id_concepto} hrs={h.horas_reportadas}")
    if len(duplicar) > 20:
        print(f"    ... y {len(duplicar)-20} más")

print(f"\n{'='*60}")
confirm = input("¿Confirmar migración? (s/N): ").strip().lower()
if confirm != "s":
    print("Cancelado.")
    raise SystemExit(0)

# ── 5. Ejecutar migración ─────────────────────────────────────────────────────
if mover:
    HoraExtra.query.filter(HoraExtra.id.in_(mover)).update(
        {"corte_id": destino.id}, synchronize_session=False
    )
    print(f"  ✓ {len(mover)} horas reasignadas al corte '{destino.nombre}'")

# Los duplicados: poner corte_id=NULL para no borrarlos (quedan sueltos)
if duplicar:
    HoraExtra.query.filter(HoraExtra.id.in_(duplicar)).update(
        {"corte_id": None}, synchronize_session=False
    )
    print(f"  ⚠  {len(duplicar)} horas duplicadas → corte_id=NULL (revisar si se deben eliminar)")

# ── 6. Eliminar corte origen (ya sin horas) ───────────────────────────────────
db.session.delete(origen)
db.session.commit()
print(f"  ✓ Corte origen ID={origen.id} eliminado")
print(f"\n✅ Migración completada. Solo queda el corte '{destino.nombre}' (ID={destino.id}).")
print(f"{'='*60}\n")

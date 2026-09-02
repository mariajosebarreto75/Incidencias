from flask import Flask, redirect, url_for
from sqlalchemy import text

from config import Config

from app.extensions import db, migrate, login_manager, scheduler
from app.models.user import User
from app.models.distribucion_operativa import DistribucionOperativa
from app.models.contrato import Contrato
from app.models.persona import Persona
from app.models.meta_operativa import MetaOperativa
from app.models.parametro_neo import ParametroNeo
from app.models.tipo_desvio import TipoDesvio
from app.models.reporte_operacional import ReporteOperacional
from app.models.user_contrato import UserContrato
from app.models.recurso_contrato import RecursoContrato
from app.models.placa_contrato import PlacaContrato
from app.models.actividad import Actividad
from app.models.accion_tomar import AccionTomar
from app.models.parametro_coor import ParametroCoor
from app.models.alerta_gps import AlertaGPS
from app.models.notificacion import Notificacion
from app.models.hora_extra import HoraExtra
from app.models.supervisor import Supervisor
from app.models.he_corte import HeCorte
from app.models.he_config import HeConfig
from app.models.semaforo import SemaforoCalificacion

from app.routes.auth import auth
from app.routes.dashboard import dashboard
from app.routes.coordinador import coordinador
from app.routes.neo import neo
from app.routes.admin import admin_bp
from app.routes.notificaciones import notif_bp
from app.routes.horas_extras import he_bp
from app.routes.parqueadero import park_bp
from app.models.parqueadero import ParqueaderoRegistro


# Lock de Postgres para que, con gunicorn -w N, solo un worker arranque el
# scheduler (si no, cada worker corre su propia copia y los jobs se disparan
# N veces por ciclo). La conexión se mantiene abierta a propósito: el lock
# se libera automáticamente cuando el worker muere y esa conexión se cierra.
_SCHEDULER_LOCK_ID = 727100501
_scheduler_lock_conn = None

_MIGRACIONES = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_dashboard BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS permisos TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE horas_extras ADD COLUMN IF NOT EXISTS supervisor VARCHAR(200)",
    "ALTER TABLE horas_extras ADD COLUMN IF NOT EXISTS valor_hora NUMERIC(14,2)",
    "ALTER TABLE horas_extras ALTER COLUMN estado TYPE VARCHAR(30)",
    "ALTER TABLE horas_extras ALTER COLUMN autorizacion_neo TYPE VARCHAR(30)",
    # Migrar supervisores a relación M2M (eliminar columna vieja si existe)
    "ALTER TABLE supervisores DROP COLUMN IF EXISTS contrato_id",
    "ALTER TABLE horas_extras ADD COLUMN IF NOT EXISTS placa VARCHAR(20)",
    "ALTER TABLE horas_extras ADD COLUMN IF NOT EXISTS hora_inicio VARCHAR(10)",
    "ALTER TABLE horas_extras ADD COLUMN IF NOT EXISTS hora_fin VARCHAR(10)",
]

_SUPERVISORES_SEED = [
    "ALVAREZ BUSTAMANTE PEDRO ANTONIO", "ARANAGA QUINTERO JULIAN ANDRES",
    "BOLANOS PAZ PEDRO LUIS", "ARAUJO CALERO JAIME ANDRES",
    "MARULANDA ROMERO BRAHIAM DANIEL", "OSPINA CORTES NICOLAS",
    "TORRES RUBIO YERLEY", "CANIZALES RAMIREZ JULIAN ANDRES",
    "CARMONA SANCHEZ JONNIER ALBERTO", "CASTILLO MEDINA LUISA FERNANDA",
    "LOSADA REINOSO DANIEL ALEJANDRO", "RODRIGUEZ GODOY ANDREA",
    "SALAZAR MENDOZA SAMANTA", "DELGADO RODRIGUEZ ANDRES CAMILO",
    "DONOSO PAVA CAMILO ANDRES", "ECHEVERRY LEAL EDER",
    "ASCENCIO LEYTON DIEGO ALEJANDRO", "FABIAN ROGELES ARIAS",
    "FRANCO AVALO MICHAEL CRISTHIAN", "GALEANO FRANCO ALEJANDRO",
    "BARENO FERRO BRAYAN JOAQUIN", "GUSTAVO ADOLFO FORERO GONZALEZ",
    "GUZMAN WHILINTONG", "HERNANDEZ ORTIZ FRANCISCO JAVIER",
    "HERNANDEZ TUTA HAMILTON RICARDO", "LEAL DUCUARA SANIL",
    "LLANOS LASSO DIEGO RAUL", "LOPEZ MORALES CRISTHIAN ANDRES",
    "CASTRO SOTELO YUDY PAOLA", "MARIN ESTRADA FERNAN",
    "CONDE CARRENO CRISTIAN CAMILO", "MAZUERA CORREA CAMILO",
    "MENDEZ CARTAGENA JESSIKA PAOLA", "MENDEZ HERNANDEZ VICTOR AUGUSTO",
    "MOLINA CASTRO JULIAN ANDRES", "MORALES BURITICA PEDRO ALEJANDRO",
    "NORENA MANZANO STHEFANY", "CONDE CERQUERA DIEGO FERNANDO",
    "ORTIZ ORTEGA EUDIS JESUS", "ORTIZ RIVAS NEDERLAN",
    "OSPINA REINOSA OSCAR DANILO", "ESCOBAR BARCO BRIGGIT",
    "OVALLE SANTOS JHON EDINSON FERNANDO", "PALMA GOMEZ YEISSON ANDRES",
    "GOMEZ HERRERA CLAUDIA JAZMIN", "RETAMOZO MAGREGO DANNA VANESSA",
    "NUNEZ NUSTES LUIS MIGUEL", "RODRIGUEZ GALVIS HUGO ARMANDO",
    "RINCON ALAPE JOSE ALIRIO", "ROLON REDONDO JORGE HUMBERTO",
    "ROMERO LIZARRALDE DIEGO ARMANDO", "ROPERO CANIZARES DIEGO ARMANDO",
    "SAENZ PRIETO CARLOS ARMANDO", "AMORTEGUI AGUIRRE WILLIAM STID",
    "SALDANA OREJUELA CARMEN INES", "SANCHEZ MOYA ERIKA PATRICIA",
    "SANTANDER ORTIZ JUAN SEBASTIAN", "TORRES ARENAS CRISTOBAL",
    "TORRES ARIAS ALEXANDER", "PEDROZA ANAZCO LAURA LIZETH",
    "TOVAR MIRA LEONARDO", "VANEGAS AREVALO RODRIGO ALBEIRO",
    "VIDAL CASTANEDA KAREN JULIETH", "VILLEGAS OLMOS CRISTHIAN DAVID",
    "ZAPATA ARANGO JOSE BERTULIO", "ALVARADO LEANDRO",
    "PICON AGUILAR JOHANA MARCELA", "PEREZ VASQUEZ JARED DAVID",
    "CASTRO LUIS FERNANDO",
]


def _seed_supervisores():
    try:
        if Supervisor.query.count() == 0:
            for nombre in _SUPERVISORES_SEED:
                db.session.add(Supervisor(nombre=nombre))
            db.session.commit()
            print(f"[Seed] {len(_SUPERVISORES_SEED)} supervisores insertados")
    except Exception as e:
        db.session.rollback()
        print(f"[Seed supervisores] Error: {e}")


def _auto_migrar():
    try:
        for sql in _MIGRACIONES:
            db.session.execute(text(sql))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[Migración] Error: {e}")


def _tiene_lock_scheduler(app):
    global _scheduler_lock_conn
    try:
        with app.app_context():
            conn = db.engine.connect()
            adquirido = conn.execute(
                text("SELECT pg_try_advisory_lock(:id)"), {"id": _SCHEDULER_LOCK_ID}
            ).scalar()
    except Exception as e:
        # Si la BD no está disponible al arrancar, este worker simplemente
        # no corre el scheduler en vez de tumbar el arranque de toda la app.
        print(f"[Scheduler] No se pudo adquirir el lock ({e}); scheduler deshabilitado en este worker")
        return False
    if adquirido:
        _scheduler_lock_conn = conn
        return True
    conn.close()
    return False


def create_app():
    app = Flask(
        __name__,
        template_folder='app/templates',
        static_folder='app/static'
    )

    app.config.from_object(Config)

    # Extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Crea tablas nuevas y aplica migraciones de columnas (seguro con IF NOT EXISTS)
    with app.app_context():
        db.create_all()
        _auto_migrar()
        _seed_supervisores()

    # Scheduler — sincroniza alertas GPS cada 5 minutos
    import os
    app.config["SCHEDULER_API_ENABLED"] = False
    if not scheduler.running and _tiene_lock_scheduler(app):
        scheduler.init_app(app)

        @scheduler.task("interval", id="sync_alertas_gps", minutes=5, misfire_grace_time=60)
        def job_sync_alertas():
            with app.app_context():
                from app.services.sincronizar_alertas import sincronizar
                sincronizar()

        # Sincroniza el plan del día automáticamente cada 10 minutos
        @scheduler.task("interval", id="sync_plan_gps", minutes=10, misfire_grace_time=60)
        def job_sync_plan():
            with app.app_context():
                from app.services.sincronizar_plan import sincronizar_plan
                sincronizar_plan()  # sin args → hoy

        # Purga mensual: el día 1 de cada mes elimina alertas del mes anterior
        @scheduler.task("cron", id="purga_alertas_mes_anterior", day=1, hour=2, minute=0)
        def job_purga_alertas():
            with app.app_context():
                from datetime import date as _date
                from app.extensions import db as _db
                from app.models.alerta_gps import AlertaGPS as _Alerta
                hoy = _date.today()
                # Primer día del mes actual → todo lo anterior se elimina
                inicio_mes_actual = hoy.replace(day=1)
                eliminadas = _Alerta.query.filter(
                    _db.func.date(_Alerta.triggered_at) < inicio_mes_actual
                ).delete(synchronize_session=False)
                _db.session.commit()
                print(f"[Purga GPS] {eliminadas} alertas del mes anterior eliminadas ({hoy})")

        # Evita doble arranque con el reloader de Flask en modo debug
        if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            scheduler.start()
            # Sincronización inicial al arrancar para que los datos estén disponibles de inmediato
            try:
                with app.app_context():
                    from app.services.sincronizar_plan import sincronizar_plan
                    resultado = sincronizar_plan()
                    print(f"[Plan GPS] Sync inicial: {resultado}")
            except Exception as e:
                print(f"[Plan GPS] Sync inicial falló: {e}")

    # Blueprints
    app.register_blueprint(auth)
    app.register_blueprint(dashboard)
    app.register_blueprint(coordinador)
    app.register_blueprint(neo)
    app.register_blueprint(admin_bp)
    app.register_blueprint(notif_bp)
    app.register_blueprint(he_bp)
    app.register_blueprint(park_bp)

    # Login manager
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.route("/")
    def home():
        return redirect(url_for("auth.login"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

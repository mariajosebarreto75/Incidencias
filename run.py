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

from app.routes.auth import auth
from app.routes.dashboard import dashboard
from app.routes.coordinador import coordinador
from app.routes.neo import neo
from app.routes.admin import admin_bp
from app.routes.notificaciones import notif_bp


# Lock de Postgres para que, con gunicorn -w N, solo un worker arranque el
# scheduler (si no, cada worker corre su propia copia y los jobs se disparan
# N veces por ciclo). La conexión se mantiene abierta a propósito: el lock
# se libera automáticamente cuando el worker muere y esa conexión se cierra.
_SCHEDULER_LOCK_ID = 727100501
_scheduler_lock_conn = None


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

        # Sincroniza el plan del día desde GPS Monitor todos los días a las 5:30 AM
        @scheduler.task("cron", id="sync_plan_gps", hour=5, minute=30, misfire_grace_time=300)
        def job_sync_plan():
            with app.app_context():
                from app.services.sincronizar_plan import sincronizar_plan
                sincronizar_plan()

        # Evita doble arranque con el reloader de Flask en modo debug
        if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            scheduler.start()

    # Blueprints
    app.register_blueprint(auth)
    app.register_blueprint(dashboard)
    app.register_blueprint(coordinador)
    app.register_blueprint(neo)
    app.register_blueprint(admin_bp)
    app.register_blueprint(notif_bp)

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

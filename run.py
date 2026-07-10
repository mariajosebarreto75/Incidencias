from flask import Flask, redirect, url_for

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
    if not scheduler.running:
        scheduler.init_app(app)

        @scheduler.task("interval", id="sync_alertas_gps", minutes=5, misfire_grace_time=60)
        def job_sync_alertas():
            with app.app_context():
                from app.services.sincronizar_alertas import sincronizar
                sincronizar()

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

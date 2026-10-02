# Incidencias NEO — Hesego Ingeniería

Aplicación web de gestión de incidencias operacionales para analistas de campo (NEO).

Desplegado en producción: https://neohesego.com

## Stack

- **Backend**: Python 3.13 + Flask 3 + SQLAlchemy 2 + PostgreSQL
- **Autenticación**: Flask-Login con cambio obligatorio de contraseña al primer ingreso
- **Programación de tareas**: Flask-APScheduler (sincronización GPS, preoperacionales, escalamientos)
- **Servidor de producción**: Gunicorn 4 workers + Nginx reverse proxy en Docker

## Roles

| Rol | Acceso |
|-----|--------|
| `admin` | Panel de administración completo |
| `neo` | Panel de reportes operacionales y compromisos |
| `coordinador` | Dashboard de coordinación, distribución operativa |
| `director` / `supervisor` | Mismo acceso que coordinador |
| `gerente` | Hub de dashboards gerenciales |
| `parqueadero` | Registro de vehículos |
| `admin_parqueadero` | Administración de parqueadero |

## Configuración local

```bash
# 1. Crear entorno virtual e instalar dependencias
python -m venv env
source env/bin/activate  # Windows: env\Scripts\activate
pip install -r requirements.txt

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con los valores reales

# 3. Arrancar (crea tablas y aplica migraciones automáticamente)
python run.py
```

## Despliegue en producción

```bash
# En el servidor (100.76.63.20)
docker compose up -d --build
```

Las migraciones de esquema se aplican automáticamente al arrancar (`run.py::_auto_migrar`).
No se usa `flask db upgrade` en producción.

## Estructura

```
app/
├── routes/      # Blueprints: auth, admin, neo, coordinador, dashboard,
│                #             horas_extras, parqueadero, compromisos, escalamiento
├── models/      # Modelos SQLAlchemy
├── services/    # Lógica de negocio: GPS, escalamientos, preoperacionales
├── templates/   # Plantillas Jinja2
└── static/      # CSS, JS, vendor libs
scripts/         # Utilidades de migración y mantenimiento (uso manual)
```

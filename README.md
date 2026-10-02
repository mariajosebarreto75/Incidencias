# Incidencias NEO — Hesego Ingeniería

Aplicación web de gestión de incidencias operacionales, reportes de campo, horas extras, compromisos y monitoreo GPS para Hesego Ingeniería.

**Producción:** https://neohesego.com

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.13 + Flask 3 + SQLAlchemy 2 |
| Base de datos | PostgreSQL (servidor 100.76.63.20) |
| Autenticación | Flask-Login — cambio obligatorio de contraseña al primer ingreso |
| Tareas programadas | Flask-APScheduler (sincronización GPS, escalamientos, preoperacionales) |
| Producción | Gunicorn 4 workers + Nginx reverse proxy, orquestado con Docker Compose |

---

## Roles

| Rol | Panel de inicio | Acceso |
|-----|----------------|--------|
| `admin` | Panel administrativo | Gestión completa: usuarios, contratos, parámetros, configuración HE, auditoría |
| `neo` | Home NEO | Reportes operacionales, validación, distribución, compromisos, alertas GPS |
| `coordinador` | Dashboard coordinador | Reportes, distribución operativa, semáforo, preoperacionales, compromisos |
| `director` | Dashboard coordinador | Igual que coordinador |
| `supervisor` | Panel supervisor | Acceso granular configurado por admin: HE, reportes NEO, semáforo, preoperacionales, BI |
| `gerente` | Hub de dashboards | Dashboards (Horas Extras, Preoperacionales), compromisos — sin notificaciones |

---

## Módulos principales

- **Reportes operacionales** — creación, validación (conforme/no conforme) y seguimiento de incidencias de campo
- **Horas extras** — registro, validación NEO, conciliación y cortes por contrato
- **Compromisos** — gestión de compromisos por reunión y contrato, checklist de seguimiento
- **Semáforo** — estado de actividades por contrato con indicadores de calificación
- **Preoperacionales** — inspecciones diarias de vehículos por sede y contrato
- **Escalamientos** — flujo de escalamiento de incidencias con respuesta NEO
- **Alertas GPS** — monitoreo de alertas del sistema GPS externo (solo roles `neo` / `admin`)
- **Distribución operativa** — asignación de recursos y personal por contrato

---

## Configuración local

```bash
# 1. Entorno virtual
python -m venv env
env\Scripts\activate          # Windows
# source env/bin/activate     # Linux/Mac

# 2. Dependencias
pip install -r requirements.txt

# 3. Variables de entorno
cp .env.example .env
# Editar .env con los valores reales (ver .env.example)

# 4. Arrancar (aplica migraciones automáticamente)
python run.py
```

> **Nota:** Las migraciones de esquema se aplican en `run.py::_auto_migrar` al arrancar.  
> No se usa `flask db upgrade` — no hay Alembic en este proyecto.

---

## Despliegue en producción

```bash
# 1. Push desde local
git push origin main

# 2. En el servidor (100.76.63.20)
git pull origin main
docker compose up --build -d
```

Los contenedores se reconstruyen con la nueva imagen y las migraciones se aplican automáticamente al iniciar la app.

---

## Estructura del proyecto

```
incidencias_neo/
├── run.py                    # Punto de entrada, migraciones automáticas, scheduler
├── config.py                 # Configuración Flask (env vars)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── app/
    ├── extensions.py         # db, login_manager, scheduler
    ├── models/               # Modelos SQLAlchemy (uno por entidad)
    │   ├── user.py
    │   ├── contrato.py
    │   ├── reporte_operacional.py
    │   ├── hora_extra.py
    │   ├── compromiso.py
    │   ├── semaforo.py
    │   ├── alerta_gps.py
    │   └── ...
    ├── routes/               # Blueprints Flask
    │   ├── auth.py           # Login, logout, cambio de contraseña
    │   ├── admin.py          # Panel admin (admin_bp)
    │   ├── neo.py            # Panel NEO, alertas GPS
    │   ├── coordinador.py    # Dashboard coordinador y supervisor
    │   ├── dashboard.py      # Hub de dashboards (gerente)
    │   ├── compromisos.py    # Módulo de compromisos (compromisos_bp)
    │   ├── horas_extras.py   # Módulo HE (he_bp)
    │   ├── escalamiento.py   # Escalamientos (esc_bp)
    │   └── notificaciones.py # API de notificaciones (notif_bp)
    ├── services/             # Lógica de negocio
    │   ├── gps_monitor.py
    │   ├── escalamiento_service.py
    │   ├── preoperacionales_service.py
    │   └── email_service.py
    ├── templates/            # Plantillas Jinja2 por rol/módulo
    │   ├── login.html
    │   ├── admin/
    │   ├── neo/
    │   ├── coordinador/
    │   ├── supervisor/
    │   ├── gerente/
    │   ├── dashboard/
    │   ├── compromisos/
    │   ├── horas_extras/
    │   ├── escalamiento/
    │   └── auth/
    └── static/
        ├── css/              # Estilos por módulo
        ├── js/               # Scripts por módulo
        ├── img/              # Logos e imágenes
        └── vendor/           # Bootstrap, Tabulator, Handsontable, XLSX
```

---

## Variables de entorno requeridas

Ver `.env.example` para la lista completa. Las principales:

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | Cadena de conexión PostgreSQL |
| `SECRET_KEY` | Clave secreta Flask |
| `MAIL_*` | Configuración SMTP para notificaciones |
| `GPS_API_*` | URL y credenciales del sistema GPS externo |
| `PREOP_*` | URL y credenciales del sistema de preoperacionales |

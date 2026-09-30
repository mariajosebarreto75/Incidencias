import os

from dotenv import load_dotenv


load_dotenv()


class Config:

    SECRET_KEY = os.getenv(
        "SECRET_KEY"
    )

    SQLALCHEMY_DATABASE_URI = (

        f"postgresql://"

        f"{os.getenv('DB_USER')}:"

        f"{os.getenv('DB_PASSWORD')}@"

        f"{os.getenv('DB_HOST')}:"

        f"{os.getenv('DB_PORT')}/"

        f"{os.getenv('DB_NAME')}"

    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Máximo 20 MB por request (cubre imágenes grandes de evidencias)
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024

    # Meta WhatsApp Cloud API (escalamiento de incidencias)
    META_WHATSAPP_TOKEN    = os.getenv("META_WHATSAPP_TOKEN", "")
    META_PHONE_NUMBER_ID   = os.getenv("META_PHONE_NUMBER_ID", "")

    # URL pública de la app (para links en WhatsApp)
    APP_URL = os.getenv("APP_URL", "http://localhost:5000")

    # SMTP — envío de correos (código de verificación de cambio de contraseña)
    SMTP_HOST     = os.getenv("SMTP_HOST", "")
    SMTP_PORT     = os.getenv("SMTP_PORT", "587")
    SMTP_USER     = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM     = os.getenv("SMTP_FROM", "")
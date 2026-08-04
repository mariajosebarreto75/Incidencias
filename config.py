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
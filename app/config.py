import os


class Config:
    """
    Base configuration object.

    Reads from environment at *instance* creation time so that values
    loaded via python-dotenv in create_app() are honored.
    """

    def __init__(self):
        # Environment / mode
        self.ENV = os.getenv("FLASK_ENV", os.getenv("ENV", "development"))
        # In Flask 3 FLASK_ENV está deprecado, pero lo seguimos usando
        # como convencion local para distinguir desarrollo/produccion.
        self.DEBUG = bool(int(os.getenv("FLASK_DEBUG", "0"))) if os.getenv("FLASK_DEBUG") is not None else self.ENV != "production"

        # Secret key: en producción debe ir SIEMPRE por entorno
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

        # Database: en producción no permitimos caer a SQLite
        uri = os.getenv("SQLALCHEMY_DATABASE_URI")
        if uri:
            self.SQLALCHEMY_DATABASE_URI = uri
        else:
            if self.ENV == "production":
                raise RuntimeError("SQLALCHEMY_DATABASE_URI must be set in production")
            # Desarrollo: usar SQLite local por defecto
            self.SQLALCHEMY_DATABASE_URI = "sqlite:///dev.db"

        self.SQLALCHEMY_TRACK_MODIFICATIONS = False

        # CSRF tokens sin expiración estricta (manejamos riesgo con SECRET_KEY fuerte)
        self.WTF_CSRF_TIME_LIMIT = None

        # Subidas de imagen
        self.MAX_IMAGE_MB = int(os.getenv("MAX_IMAGE_MB", "2"))
        # Directorio de subidas en disco; por defecto fuera de static/
        # Ejemplos:
        #  - Local: ./uploads
        #  - Render: /opt/render/project/src/uploads
        self.UPLOADS_DIR = os.getenv("UPLOADS_DIR", "./uploads")

        # Rate limiting global por defecto
        self.RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "100 per minute")

        # Cookies de sesión seguras en producción
        if self.ENV == "production":
            self.SESSION_COOKIE_SECURE = True
            self.REMEMBER_COOKIE_SECURE = True
            self.SESSION_COOKIE_HTTPONLY = True
            self.REMEMBER_COOKIE_HTTPONLY = True

    def __call__(self):
        # Permite usar Config() como callable en app.config.from_object
        return self

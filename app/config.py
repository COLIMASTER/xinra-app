import os


class Config:
    def __call__(self):
        return self

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = None
    MAX_IMAGE_MB = int(os.getenv("MAX_IMAGE_MB", "2"))
    UPLOADS_DIR = os.getenv("UPLOADS_DIR", "./static/uploads")
    RATELIMIT_DEFAULT = "100 per minute"

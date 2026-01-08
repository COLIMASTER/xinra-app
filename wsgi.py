import os
from sqlalchemy import text
from flask_migrate import upgrade
from app import create_app
from app.extensions import db

app = create_app()


def _maybe_run_migrations():
    auto = os.getenv("AUTO_MIGRATE", "")
    if auto.lower() not in ("1", "true", "yes"):
        return
    with app.app_context():
        engine = db.engine
        if engine.dialect.name == "postgresql":
            with engine.connect() as conn:
                got_lock = conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": 982451653}).scalar()
                if not got_lock:
                    return
                upgrade()
                conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": 982451653})
        else:
            upgrade()


_maybe_run_migrations()

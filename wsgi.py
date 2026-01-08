import os
from sqlalchemy import text, inspect
from flask_migrate import upgrade, stamp
from app import create_app
from app.extensions import db

app = create_app()


def _maybe_run_migrations():
    auto = os.getenv("AUTO_MIGRATE", "")
    if auto.lower() not in ("1", "true", "yes"):
        return
    with app.app_context():
        engine = db.engine
        def _bootstrap_schema():
            created = False
            with engine.begin() as conn:
                insp = inspect(conn)
                if not insp.has_table("restaurants"):
                    db.metadata.create_all(bind=conn)
                    created = True
            if created:
                stamp(revision="head")
                return True
            return False

        if engine.dialect.name == "postgresql":
            with engine.connect() as lock_conn:
                got_lock = lock_conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": 982451653}).scalar()
                if not got_lock:
                    return
                if _bootstrap_schema():
                    lock_conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": 982451653})
                    return
                upgrade()
                lock_conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": 982451653})
        else:
            if _bootstrap_schema():
                return
            upgrade()


_maybe_run_migrations()

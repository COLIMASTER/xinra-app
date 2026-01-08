import os
from datetime import timedelta
from flask import Flask, render_template
from dotenv import load_dotenv
from .extensions import db, migrate, login_manager, csrf, limiter
from sqlalchemy import inspect
from .config import Config


def create_app():
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True, static_folder="../static", template_folder="../templates")

    app.config.from_object(Config())

    os.makedirs(app.config.get("UPLOADS_DIR", "./uploads"), exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from .routes.public import public_bp
    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.health import health_bp
    from .routes.uploads import uploads_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(uploads_bp)

    # Auto-create tables only for local SQLite dev if schema missing
    try:
        uri = str(app.config.get("SQLALCHEMY_DATABASE_URI", "") or "")
        if uri.startswith("sqlite:///") and app.config.get("ENV") != "production":
            with app.app_context():
                insp = inspect(db.engine)
                if not insp.has_table("restaurants"):
                    db.create_all()
    except Exception:
        # Don't block app start on this helper; CLI seed/migrations can be used instead
        pass

    from flask_wtf.csrf import generate_csrf
    app.jinja_env.globals['csrf_token'] = generate_csrf

    # Expose a helper to check if the current user is admin/manager of some restaurant
    @app.context_processor
    def inject_permissions():
        try:
            from flask_login import current_user
            from .models import Membership, Staff
        except Exception:
            # In case of import timing issues during app init
            return {}

        def has_admin():
            if not current_user.is_authenticated:
                return False
            return (
                Membership.query
                .filter(Membership.user_id == current_user.id, Membership.role.in_(("admin", "manager")))
                .first()
                is not None
            )

        def has_staff():
            if not current_user.is_authenticated:
                return False
            staff = (
                Staff.query
                .filter(Staff.user_id == current_user.id, Staff.active.is_(True))
                .first()
            )
            if staff:
                return True
            return (
                Membership.query
                .filter(Membership.user_id == current_user.id, Membership.role == "staff")
                .first()
                is not None
            )

        return {"has_admin": has_admin, "has_staff": has_staff}

    @app.shell_context_processor
    def make_shell_context():
        from . import models
        return {"db": db, **{name: getattr(models, name) for name in dir(models) if name[0].isupper()}}

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("errors/500.html"), 500

    app.permanent_session_lifetime = timedelta(days=30)

    return app

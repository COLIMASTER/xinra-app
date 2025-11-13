from flask import current_app
from flask_login import login_user
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import User
from ..utils.security import hash_password, verify_password


def register_user(email: str, password: str, name: str) -> User:
    user = User(email=email.lower().strip(), password_hash=hash_password(password), name=name.strip())
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError("El email ya está registrado")
    login_user(user)
    return user


def authenticate(email: str, password: str) -> User:
    user = User.query.filter_by(email=email.lower().strip()).first()
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise ValueError("Credenciales inválidas")
    login_user(user)
    return user

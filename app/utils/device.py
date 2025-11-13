import hashlib
import uuid
from flask import request, make_response
from ..models import User
from ..extensions import db


COOKIE_NAME = "device_id"


def get_device_id() -> str | None:
    return request.cookies.get(COOKIE_NAME)


def ensure_device_cookie(response):
    did = get_device_id()
    if not did:
        did = str(uuid.uuid4())
        response.set_cookie(COOKIE_NAME, did, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return did


def device_hash(device_id: str) -> str:
    return hashlib.sha256(device_id.encode()).hexdigest()


def get_or_create_guest_user() -> User:
    did = get_device_id()
    if not did:
        did = str(uuid.uuid4())
    dh = device_hash(did)
    user = User.query.filter_by(device_id_hash=dh).first()
    if not user:
        user = User(device_id_hash=dh, name="Invitado")
        db.session.add(user)
        db.session.commit()
    return user

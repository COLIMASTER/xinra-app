import hashlib
import uuid
from flask import request, g
from ..models import User
from ..extensions import db


COOKIE_NAME = "device_id"


def get_device_id() -> str | None:
    return request.cookies.get(COOKIE_NAME) or getattr(g, "device_id", None)


def ensure_device_cookie(response):
    did = request.cookies.get(COOKIE_NAME)
    if not did:
        did = getattr(g, "device_id", None) or str(uuid.uuid4())
        response.set_cookie(COOKIE_NAME, did, max_age=60 * 60 * 24 * 365, samesite="Lax")
        g.device_id = did
    return did


def device_hash(device_id: str) -> str:
    return hashlib.sha256(device_id.encode()).hexdigest()


def get_or_create_guest_user() -> User:
    did = get_device_id()
    if not did:
        did = str(uuid.uuid4())
        g.device_id = did
    dh = device_hash(did)
    user = User.query.filter_by(device_id_hash=dh).first()
    if not user:
        user = User(device_id_hash=dh, name="Guest")
        db.session.add(user)
        db.session.commit()
    return user

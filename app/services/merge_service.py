from ..extensions import db
from ..models import Tip, Review, User
from .reward_service import recalc_level


def merge_guest_into_user(guest: User, user: User):
    if guest.id == user.id:
        return
    Tip.query.filter_by(user_id=guest.id).update({"user_id": user.id})
    Review.query.filter_by(user_id=guest.id).update({"user_id": user.id})
    user.xp = (user.xp or 0) + (guest.xp or 0)
    recalc_level(user)
    db.session.delete(guest)
    db.session.commit()

from datetime import datetime
from ..extensions import db
from ..models import Tip, User
from .reward_service import add_xp


def create_tip(restaurant_id: int, staff_id: int | None, user: User | None, amount_cents: int, method_ui: str) -> Tip:
    tip = Tip(restaurant_id=restaurant_id, staff_id=staff_id, user_id=user.id if user else None, amount_cents=amount_cents, method_ui=method_ui, status="recorded", created_at=datetime.utcnow())
    db.session.add(tip)
    if user:
        add_xp(user, 10)
    db.session.commit()
    return tip

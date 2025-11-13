from ..extensions import db
from ..models import RewardTier, User


def recalc_level(user: User):
    tiers = RewardTier.query.order_by(RewardTier.threshold_xp.asc()).all()
    level = 1
    for i, t in enumerate(tiers, start=1):
        if (user.xp or 0) >= t.threshold_xp:
            level = i
    user.level = level


def add_xp(user: User, amount: int):
    user.xp = (user.xp or 0) + int(amount)
    recalc_level(user)
    db.session.add(user)

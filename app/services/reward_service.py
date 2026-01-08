from ..extensions import db
from ..models import RewardTier, User


def get_tiers():
    return RewardTier.query.order_by(RewardTier.threshold_xp.asc()).all()


def get_tier_progress(user: User | None):
    tiers = get_tiers()
    if not tiers:
        return [], None, None, 0
    xp = (user.xp if user else 0) or 0
    current = tiers[0]
    next_tier = None
    prev_thresh = tiers[0].threshold_xp
    for t in tiers:
        if xp >= t.threshold_xp:
            current = t
            prev_thresh = t.threshold_xp
        else:
            next_tier = t
            break
    progress_pct = 100
    if next_tier:
        span = max(1, next_tier.threshold_xp - prev_thresh)
        progress_pct = int(100 * ((xp - prev_thresh) / span))
    return tiers, current, next_tier, progress_pct


def recalc_level(user: User):
    tiers = get_tiers()
    if not tiers:
        user.level = 1
        return
    level = 1
    for i, t in enumerate(tiers, start=1):
        if (user.xp or 0) >= t.threshold_xp:
            level = i
    user.level = level


def add_xp(user: User, amount: int):
    user.xp = (user.xp or 0) + int(amount)
    recalc_level(user)
    db.session.add(user)

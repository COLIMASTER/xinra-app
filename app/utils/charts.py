from datetime import datetime, timedelta, date
import calendar
from sqlalchemy import func
from ..extensions import db
from ..models import Tip, Review


def tips_per_day(restaurant_id: int, days: int = 14):
    start = datetime.utcnow().date() - timedelta(days=days - 1)
    rows = (
        db.session.query(func.date(Tip.created_at), func.sum(Tip.amount_cents))
        .filter(Tip.restaurant_id == restaurant_id, Tip.created_at >= start)
        .group_by(func.date(Tip.created_at))
        .order_by(func.date(Tip.created_at))
        .all()
    )
    totals = {d: a for d, a in rows}
    labels, data = [], []
    for i in range(days):
        day = start + timedelta(days=i)
        labels.append(day.strftime("%Y-%m-%d"))
        data.append(int(totals.get(day, 0) or 0))
    return labels, data


def daily_current_previous_month(restaurant_id: int):
    """
    Returns per-day totals (in cents) for the current month and previous month.
    Labels are day numbers as strings ("1".."N"). Length is the max days between
    the two months so both series align (missing days are 0).
    """
    today = datetime.utcnow().date()
    # Current month boundaries
    cur_start = today.replace(day=1)
    if cur_start.month == 12:
        next_month = cur_start.replace(year=cur_start.year + 1, month=1, day=1)
    else:
        next_month = cur_start.replace(month=cur_start.month + 1, day=1)
    cur_end = next_month - timedelta(seconds=1)
    cur_days = calendar.monthrange(cur_start.year, cur_start.month)[1]

    # Previous month boundaries
    if cur_start.month == 1:
        prev_start = date(cur_start.year - 1, 12, 1)
    else:
        prev_start = date(cur_start.year, cur_start.month - 1, 1)
    prev_days = calendar.monthrange(prev_start.year, prev_start.month)[1]
    prev_end = date(prev_start.year, prev_start.month, prev_days)

    # Query sums grouped by date for current month
    cur_rows = (
        db.session.query(func.date(Tip.created_at), func.coalesce(func.sum(Tip.amount_cents), 0))
        .filter(
            Tip.restaurant_id == restaurant_id,
            Tip.created_at >= cur_start,
            Tip.created_at <= cur_end,
            Tip.status == "recorded",
        )
        .group_by(func.date(Tip.created_at))
        .order_by(func.date(Tip.created_at))
        .all()
    )
    # Query sums grouped by date for previous month
    prev_rows = (
        db.session.query(func.date(Tip.created_at), func.coalesce(func.sum(Tip.amount_cents), 0))
        .filter(
            Tip.restaurant_id == restaurant_id,
            Tip.created_at >= prev_start,
            Tip.created_at <= prev_end,
            Tip.status == "recorded",
        )
        .group_by(func.date(Tip.created_at))
        .order_by(func.date(Tip.created_at))
        .all()
    )
    def _coerce_key(x):
        if isinstance(x, date):
            return x
        # Expect ISO string 'YYYY-MM-DD'
        try:
            return datetime.fromisoformat(str(x)).date()
        except Exception:
            return datetime.utcfromtimestamp(0).date()

    cur_map = {_coerce_key(d): int(a or 0) for d, a in cur_rows}
    prev_map = {_coerce_key(d): int(a or 0) for d, a in prev_rows}

    total_days = max(cur_days, prev_days)
    labels = [str(i) for i in range(1, total_days + 1)]
    cur_series = []
    prev_series = []
    for i in range(1, total_days + 1):
        # Compose actual dates for mapping
        di_cur = date(cur_start.year, cur_start.month, min(i, cur_days))
        di_prev = date(prev_start.year, prev_start.month, min(i, prev_days))
        cur_series.append(cur_map.get(di_cur, 0) if i <= cur_days else 0)
        prev_series.append(prev_map.get(di_prev, 0) if i <= prev_days else 0)

    return labels, cur_series, prev_series

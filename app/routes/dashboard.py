from __future__ import annotations

from datetime import datetime, timedelta, date
from collections import defaultdict
import secrets
import string

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response
from sqlalchemy import func
from flask_login import login_required, current_user

from ..extensions import db
from ..models import (
    Restaurant,
    Staff,
    Tip,
    Review,
    Membership,
    Transfer,
    Coupon,
    User,
)
from ..services.image_service import process_and_save_image
from ..services.reward_service import add_xp, get_tier_progress
from ..utils.security import hash_password


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def _generate_random_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _generate_staff_email(name: str, restaurant: Restaurant) -> str:
    base = (name or "staff").lower()
    cleaned = []
    for ch in base:
        if ch.isalnum():
            cleaned.append(ch)
        elif ch in (" ", ".", "_", "-"):
            cleaned.append(".")
    base_name = "".join(cleaned).strip(".") or "staff"
    # Use a syntactically valid domain so that WTForms Email() validator accepts it
    domain = "example.com"
    base_email = f"{restaurant.slug}.{base_name}@{domain}"
    email = base_email
    idx = 1
    while User.query.filter_by(email=email).first() is not None:
        email = f"{restaurant.slug}.{base_name}{idx}@{domain}"
        idx += 1
    return email


def _ensure_staff_login(staff: Staff, restaurant: Restaurant) -> None:
    if staff.user_id:
        # Ensure legacy generated emails with old domains are migrated to a valid one
        if staff.user and staff.user.email and staff.user.email.endswith("@staff.local"):
            staff.user.email = _generate_staff_email(staff.name, restaurant)
            db.session.add(staff.user)
        return
    email = _generate_staff_email(staff.name, restaurant)
    raw_password = _generate_random_password()
    user = User(email=email, name=staff.name, password_hash=hash_password(raw_password))
    db.session.add(user)
    db.session.flush()
    staff.user_id = user.id
    staff.login_initial_password = raw_password
    db.session.add(staff)
    existing = (
        Membership.query.filter_by(user_id=user.id, restaurant_id=restaurant.id, role="staff")
        .order_by(Membership.id.asc())
        .first()
    )
    if not existing:
        db.session.add(Membership(user_id=user.id, restaurant_id=restaurant.id, role="staff"))


def _require_admin_restaurant() -> Restaurant:
    if not current_user.is_authenticated:
        abort(401)
    m = (
        Membership.query
        .filter(Membership.user_id == current_user.id, Membership.role.in_(("admin", "manager")))
        .order_by(Membership.id.asc())
        .first()
    )
    if not m:
        flash("You don't have admin access", "danger")
        abort(403)
    return m.restaurant


def _resolve_staff_for_user(user: User):
    staff = Staff.query.filter_by(user_id=user.id, active=True).first()
    if staff:
        return staff, Restaurant.query.get(staff.restaurant_id)
    membership = (
        Membership.query
        .filter(Membership.user_id == user.id, Membership.role == "staff")
        .order_by(Membership.id.asc())
        .first()
    )
    if not membership:
        return None, None
    restaurant = membership.restaurant or Restaurant.query.get(membership.restaurant_id)
    if not restaurant:
        return None, None
    name = (user.name or "").strip()
    candidate = None
    if name:
        candidate = (
            Staff.query
            .filter(Staff.restaurant_id == restaurant.id, Staff.active.is_(True))
            .filter(func.lower(Staff.name) == name.lower())
            .first()
        )
    if not candidate:
        candidate = Staff(restaurant_id=restaurant.id, name=name or "Staff", role="Staff", active=True, user_id=user.id)
        db.session.add(candidate)
        db.session.commit()
    else:
        candidate.user_id = user.id
        db.session.add(candidate)
        db.session.commit()
    return candidate, restaurant


def _sum_tips_q(q):
    total = 0
    for t in q:
        total += int(t.amount_cents or 0)
    return total


def _sum_amounts(rows):
    total = 0
    for row in rows:
        total += int(getattr(row, "amount_cents", 0) or 0)
    return total


def _pct_change(current: int, previous: int) -> int:
    if previous <= 0:
        return 100 if current > 0 else 0
    return int(round(((current - previous) / previous) * 100))


def _avg_rating(reviews):
    if not reviews:
        return 0.0, 0
    total = sum(int(r.rating or 0) for r in reviews)
    count = len(reviews)
    return (total / count), count


def _totals_by_day(rows, start: datetime, days: int):
    totals = [0] * days
    for row in rows:
        created = row.created_at
        if created < start:
            continue
        idx = (created.date() - start.date()).days
        if 0 <= idx < days:
            totals[idx] += int(getattr(row, "amount_cents", 0) or 0)
    return totals


def _pending_balance_for_staff(restaurant_id: int, staff_id: int) -> int:
    total = _sum_amounts(Tip.query.filter_by(restaurant_id=restaurant_id, staff_id=staff_id).all())
    sent = _sum_amounts(Transfer.query.filter_by(restaurant_id=restaurant_id, staff_id=staff_id).all())
    return max(0, total - sent)


def _build_restaurant_dashboard_context(r: Restaurant):
    now = datetime.utcnow()
    start_today = datetime(now.year, now.month, now.day)
    start_yesterday = start_today - timedelta(days=1)
    start_week = start_today - timedelta(days=start_today.weekday())
    start_last_week = start_week - timedelta(days=7)
    start_month = datetime(now.year, now.month, 1)
    next_month = datetime(now.year + (1 if now.month == 12 else 0), (now.month % 12) + 1, 1)
    days_in_month = (next_month - start_month).days

    tips_today_rows = Tip.query.filter_by(restaurant_id=r.id).filter(Tip.created_at >= start_today).all()
    tips_yesterday_rows = Tip.query.filter_by(restaurant_id=r.id).filter(Tip.created_at >= start_yesterday, Tip.created_at < start_today).all()
    tips_week_rows = Tip.query.filter_by(restaurant_id=r.id).filter(Tip.created_at >= start_week).all()
    tips_last_week_rows = Tip.query.filter_by(restaurant_id=r.id).filter(Tip.created_at >= start_last_week, Tip.created_at < start_week).all()
    tips_month_rows = Tip.query.filter_by(restaurant_id=r.id).filter(Tip.created_at >= start_month).all()

    tips_today = _sum_tips_q(tips_today_rows)
    tips_yesterday = _sum_tips_q(tips_yesterday_rows)
    tips_week = _sum_tips_q(tips_week_rows)
    tips_last_week = _sum_tips_q(tips_last_week_rows)
    tips_month = _sum_tips_q(tips_month_rows)

    tips_growth_pct = _pct_change(tips_today, tips_yesterday)
    week_growth_pct = _pct_change(tips_week, tips_last_week)

    reviews_week_rows = Review.query.filter_by(restaurant_id=r.id).filter(Review.created_at >= start_week).all()
    reviews_last_week_rows = Review.query.filter_by(restaurant_id=r.id).filter(Review.created_at >= start_last_week, Review.created_at < start_week).all()
    rating_avg_week, reviews_week_count = _avg_rating(reviews_week_rows)
    reviews_delta = reviews_week_count - len(reviews_last_week_rows)

    week_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    week_totals = _totals_by_day(tips_week_rows, start_week, 7)
    month_labels = [str(i) for i in range(1, days_in_month + 1)]
    month_totals = _totals_by_day(tips_month_rows, start_month, days_in_month)

    staff_all = Staff.query.filter_by(restaurant_id=r.id, active=True).order_by(Staff.name.asc()).all()
    totals_by_staff = defaultdict(int)
    for t in tips_week_rows:
        if t.staff_id:
            totals_by_staff[t.staff_id] += int(t.amount_cents or 0)
    ratings_by_staff = defaultdict(list)
    for rv in reviews_week_rows:
        if rv.staff_id:
            ratings_by_staff[rv.staff_id].append(int(rv.rating or 0))

    staff_metrics = []
    for st in staff_all:
        ratings = ratings_by_staff.get(st.id, [])
        rating_avg = (sum(ratings) / len(ratings)) if ratings else 0.0
        staff_metrics.append({
            "staff": st,
            "tips_total": totals_by_staff.get(st.id, 0),
            "rating_avg": rating_avg,
            "reviews_count": len(ratings),
        })
    staff_metrics.sort(key=lambda item: item["tips_total"], reverse=True)
    rank_labels = ["Gold Performer", "Silver Star", "Bronze Highlight"]
    top_staff = []
    for idx, item in enumerate(staff_metrics[:3]):
        item["rank_label"] = rank_labels[idx] if idx < len(rank_labels) else "Top Performer"
        top_staff.append(item)

    recent_reviews = Review.query.filter_by(restaurant_id=r.id).order_by(Review.created_at.desc()).limit(12).all()

    today_label = now.strftime("%Y-%m-%d")

    return {
        "tips_today": tips_today,
        "tips_week": tips_week,
        "tips_month": tips_month,
        "tips_growth_pct": tips_growth_pct,
        "week_growth_pct": week_growth_pct,
        "rating_avg_week": rating_avg_week,
        "reviews_week_count": reviews_week_count,
        "reviews_delta": reviews_delta,
        "week_labels": week_labels,
        "week_totals": week_totals,
        "month_labels": month_labels,
        "month_totals": month_totals,
        "total_tips": tips_week,
        "top_staff": top_staff,
        "today_label": today_label,
        "recent_reviews": recent_reviews,
    }


def _build_staff_dashboard_context(r: Restaurant, s: Staff):
    ctx = _build_restaurant_dashboard_context(r)
    pending_balance = _pending_balance_for_staff(r.id, s.id)

    user = s.user
    current_tier = None
    next_tier = None
    progress_pct = 0
    if user:
        _, current_tier, next_tier, progress_pct = get_tier_progress(user)

    ctx.update({
        "pending_balance": pending_balance,
        "current_tier": current_tier,
        "next_tier": next_tier,
        "progress_pct": progress_pct,
        "user_xp": user.xp if user else 0,
    })
    return ctx


@dashboard_bp.route("/restaurant")
@login_required
def restaurant_view():
    r = _require_admin_restaurant()
    ctx = _build_restaurant_dashboard_context(r)
    return render_template(
        "dashboard/restaurant.html",
        restaurant=r,
        **ctx,
    )


@dashboard_bp.route("/restaurant/logo", methods=["POST"]) 
@login_required
def restaurant_logo():
    r = _require_admin_restaurant()
    file = request.files.get("logo")
    if not file:
        flash("Select an image", "danger")
        return redirect(url_for("dashboard.restaurant_view"))
    try:
        url, _, _ = process_and_save_image(file)
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("dashboard.restaurant_view"))
    r.logo_url = url
    db.session.add(r)
    db.session.commit()
    flash("Logo updated", "success")
    return redirect(url_for("dashboard.restaurant_view"))


@dashboard_bp.route("/restaurant/logo/delete", methods=["POST"]) 
@login_required
def restaurant_logo_delete():
    r = _require_admin_restaurant()
    r.logo_url = None
    db.session.add(r)
    db.session.commit()
    flash("Logo removed", "info")
    return redirect(url_for("dashboard.restaurant_view"))


@dashboard_bp.route("/payouts", methods=["GET", "POST"]) 
@login_required
def payouts_view():
    r = _require_admin_restaurant()

    # Compute pending per staff
    totals_by_staff: dict[int, int] = defaultdict(int)
    for t in Tip.query.filter_by(restaurant_id=r.id).all():
        if t.staff_id:
            totals_by_staff[t.staff_id] += int(t.amount_cents or 0)
    sent_by_staff: dict[int, int] = defaultdict(int)
    for tr in Transfer.query.filter_by(restaurant_id=r.id).all():
        if tr.staff_id:
            sent_by_staff[tr.staff_id] += int(tr.amount_cents or 0)

    staff_all = Staff.query.filter_by(restaurant_id=r.id, active=True).order_by(Staff.name.asc()).all()
    rows = []
    for s in staff_all:
        pending = totals_by_staff.get(s.id, 0) - sent_by_staff.get(s.id, 0)
        rows.append((s, max(0, pending)))

    if request.method == "POST":
        staff_id = request.form.get("staff_id", type=int)
        if staff_id:
            pending_map = {s.id: total for s, total in rows}
            amt = pending_map.get(staff_id, 0)
            if amt > 0:
                tr = Transfer(restaurant_id=r.id, staff_id=staff_id, amount_cents=amt, status="sent")
                db.session.add(tr)
                db.session.commit()
                flash("Transfer created", "success")
            else:
                flash("Nothing pending for this staff", "info")
        return redirect(url_for("dashboard.payouts_view"))

    transfers = Transfer.query.filter_by(restaurant_id=r.id).order_by(Transfer.created_at.desc()).limit(20).all()
    return render_template("dashboard/payouts.html", restaurant=r, rows=rows, transfers=transfers)


@dashboard_bp.route("/coupons")
@login_required
def coupons_manage():
    r = _require_admin_restaurant()
    coupons = Coupon.query.filter_by(restaurant_id=r.id).order_by(Coupon.created_at.desc()).all()
    return render_template("dashboard/coupons.html", restaurant=r, coupons=coupons)


@dashboard_bp.route("/coupons/create", methods=["POST"]) 
@login_required
def coupons_create():
    r = _require_admin_restaurant()
    title = (request.form.get("title") or "").strip()
    required_xp = request.form.get("required_xp", type=int) or 0
    description = (request.form.get("description") or "").strip() or None
    active = True if request.form.get("active") else False
    if not title:
        flash("Title required", "danger")
        return redirect(url_for("dashboard.coupons_manage"))
    c = Coupon(restaurant_id=r.id, title=title, description=description, required_xp=required_xp, active=active)
    db.session.add(c)
    db.session.commit()
    flash("Coupon created", "success")
    return redirect(url_for("dashboard.coupons_manage"))


@dashboard_bp.route("/coupons/<int:coupon_id>/update", methods=["POST"]) 
@login_required
def coupons_update(coupon_id: int):
    r = _require_admin_restaurant()
    c = Coupon.query.filter_by(id=coupon_id, restaurant_id=r.id).first_or_404()
    c.title = (request.form.get("title") or c.title).strip()
    c.description = (request.form.get("description") or "").strip() or None
    c.active = True if request.form.get("active") else False
    db.session.add(c)
    db.session.commit()
    flash("Coupon updated", "success")
    return redirect(url_for("dashboard.coupons_manage"))


@dashboard_bp.route("/coupons/<int:coupon_id>/delete", methods=["POST"]) 
@login_required
def coupons_delete(coupon_id: int):
    r = _require_admin_restaurant()
    c = Coupon.query.filter_by(id=coupon_id, restaurant_id=r.id).first_or_404()
    db.session.delete(c)
    db.session.commit()
    flash("Coupon deleted", "info")
    return redirect(url_for("dashboard.coupons_manage"))


@dashboard_bp.route("/breakdown")
@login_required
def breakdown_view():
    r = _require_admin_restaurant()
    tab = request.args.get("tab", "tips")
    export = request.args.get("export")
    if tab == "reviews":
        reviews = Review.query.filter_by(restaurant_id=r.id).order_by(Review.created_at.desc()).limit(200).all()
        if export == "csv":
            lines = ["id,created_at,rating,comment,staff_id,user_id"] + [
                f"{rv.id},{rv.created_at},{rv.rating},\"{(rv.comment or '').replace('\\', ' ').replace('"', ' ')}\",{rv.staff_id or ''},{rv.user_id or ''}" for rv in reviews
            ]
            return Response("\n".join(lines), mimetype="text/csv")
        return render_template("dashboard/breakdown.html", restaurant=r, tab="reviews", reviews=reviews)
    else:
        tips = Tip.query.filter_by(restaurant_id=r.id).order_by(Tip.created_at.desc()).limit(200).all()
        if export == "csv":
            lines = ["id,created_at,amount_cents,method_ui,staff_id,user_id"] + [
                f"{t.id},{t.created_at},{t.amount_cents},{t.method_ui},{t.staff_id or ''},{t.user_id or ''}" for t in tips
            ]
            return Response("\n".join(lines), mimetype="text/csv")
    return render_template("dashboard/breakdown.html", restaurant=r, tab="tips", tips=tips)


@dashboard_bp.route("/me/staff")
@login_required
def my_staff_panel():
    s, r = _resolve_staff_for_user(current_user)
    if not s or not r:
        flash("No staff profile associated with this account", "info")
        return redirect(url_for("auth.profile"))
    ctx = _build_staff_dashboard_context(r, s)
    return render_template("dashboard/staff.html", restaurant=r, staff=s, **ctx)


@dashboard_bp.route("/staff/<int:staff_id>")
@login_required
def staff_view(staff_id: int):
    r = _require_admin_restaurant()
    s = Staff.query.filter_by(id=staff_id, restaurant_id=r.id).first_or_404()
    ctx = _build_staff_dashboard_context(r, s)
    return render_template("dashboard/staff.html", restaurant=r, staff=s, **ctx)


@dashboard_bp.route("/me/breakdown")
@login_required
def staff_breakdown():
    s, r = _resolve_staff_for_user(current_user)
    if not s or not r:
        flash("No staff profile associated with this account", "info")
        return redirect(url_for("auth.profile"))
    now = datetime.utcnow()
    start_today = datetime(now.year, now.month, now.day)
    start_week = start_today - timedelta(days=start_today.weekday())

    tips_week_all = Tip.query.filter_by(restaurant_id=r.id).filter(Tip.created_at >= start_week).all()
    totals_by_staff = defaultdict(int)
    pooled_week = 0
    for t in tips_week_all:
        if t.staff_id:
            totals_by_staff[t.staff_id] += int(t.amount_cents or 0)
        else:
            pooled_week += int(t.amount_cents or 0)

    reviews_week_all = Review.query.filter_by(restaurant_id=r.id).filter(Review.created_at >= start_week).all()
    ratings_by_staff = defaultdict(list)
    for rv in reviews_week_all:
        if rv.staff_id:
            ratings_by_staff[rv.staff_id].append(int(rv.rating or 0))

    staff_all = Staff.query.filter_by(restaurant_id=r.id, active=True).order_by(Staff.name.asc()).all()
    earnings_list = []
    for st in staff_all:
        ratings = ratings_by_staff.get(st.id, [])
        rating_avg = (sum(ratings) / len(ratings)) if ratings else 0.0
        earnings_list.append({
            "staff": st,
            "tips_total": totals_by_staff.get(st.id, 0),
            "rating_avg": rating_avg,
            "reviews_count": len(ratings),
        })
    earnings_list.sort(key=lambda item: item["tips_total"], reverse=True)

    reviews_week_staff = Review.query.filter_by(restaurant_id=r.id, staff_id=s.id).filter(Review.created_at >= start_week).order_by(Review.created_at.desc()).all()
    rating_avg_week, _ = _avg_rating(reviews_week_staff)
    recent_feedback = reviews_week_staff[:12]

    direct_week = totals_by_staff.get(s.id, 0)
    today_label = now.strftime("%Y-%m-%d")
    message = f"Keep it up, {s.name}, you're on track for top performer this month."

    return render_template(
        "dashboard/breakdown_staff.html",
        restaurant=r,
        staff=s,
        pooled_week=pooled_week,
        direct_week=direct_week,
        rating_avg_week=rating_avg_week,
        earnings_list=earnings_list,
        recent_feedback=recent_feedback,
        today_label=today_label,
        message=message,
    )


@dashboard_bp.route("/me/transfer", methods=["POST"])
@login_required
def staff_transfer():
    s, r = _resolve_staff_for_user(current_user)
    if not s or not r:
        flash("No staff profile associated with this account", "info")
        return redirect(url_for("auth.profile"))
    pending = _pending_balance_for_staff(r.id, s.id)
    if pending <= 0:
        flash("No pending balance to transfer", "info")
        return redirect(url_for("dashboard.my_staff_panel"))
    tr = Transfer(restaurant_id=r.id, staff_id=s.id, amount_cents=pending, status="sent", created_at=datetime.utcnow())
    db.session.add(tr)
    add_xp(current_user, 10)
    db.session.commit()
    return redirect(url_for("dashboard.transfer_complete"))


@dashboard_bp.route("/me/transfer/complete")
@login_required
def transfer_complete():
    s, r = _resolve_staff_for_user(current_user)
    if not s or not r:
        flash("No staff profile associated with this account", "info")
        return redirect(url_for("auth.profile"))
    now = datetime.utcnow()
    start_month = datetime(now.year, now.month, 1)
    transfer_count = (
        Transfer.query.filter_by(restaurant_id=r.id, staff_id=s.id)
        .filter(Transfer.created_at >= start_month)
        .count()
    )
    return render_template("dashboard/transfer_complete.html", restaurant=r, staff=s, transfer_count=transfer_count)


@dashboard_bp.route("/staff/manage")
@login_required
def staff_manage():
    r = _require_admin_restaurant()
    staff_query = Staff.query.filter_by(restaurant_id=r.id).order_by(Staff.name.asc())
    staff_list = staff_query.all()
    changed = False
    for s in staff_list:
        before_email = s.user.email if s.user else None
        before_user_id = s.user_id
        _ensure_staff_login(s, r)
        if s.user_id != before_user_id or (s.user and s.user.email != before_email):
            changed = True
    if changed:
        db.session.commit()
        staff_list = staff_query.all()
    return render_template("dashboard/staff_manage.html", restaurant=r, staff_list=staff_list)


@dashboard_bp.route("/staff/create", methods=["POST"]) 
@login_required
def staff_create():
    r = _require_admin_restaurant()
    name = (request.form.get("name") or "").strip()
    role = (request.form.get("role") or "").strip() or None
    bio = (request.form.get("bio") or "").strip() or None
    if not name:
        flash("Name required", "danger")
        return redirect(url_for("dashboard.staff_manage"))
    avatar_file = request.files.get("avatar")
    avatar_url = None
    if avatar_file and (avatar_file.filename or "").strip():
        try:
            avatar_url, _, _ = process_and_save_image(avatar_file)
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("dashboard.staff_manage"))
    s = Staff(restaurant_id=r.id, name=name, role=role, bio=bio, avatar_url=avatar_url)
    db.session.add(s)
    db.session.flush()
    _ensure_staff_login(s, r)
    db.session.commit()
    flash("Staff member created", "success")
    return redirect(url_for("dashboard.staff_manage"))


@dashboard_bp.route("/staff/<int:staff_id>/update", methods=["POST"]) 
@login_required
def staff_update(staff_id: int):
    r = _require_admin_restaurant()
    s = Staff.query.filter_by(id=staff_id, restaurant_id=r.id).first_or_404()
    s.name = (request.form.get("name") or s.name).strip()
    s.role = (request.form.get("role") or "").strip() or None
    s.bio = (request.form.get("bio") or "").strip() or None
    s.active = True if request.form.get("active") else False
    avatar_file = request.files.get("avatar")
    if avatar_file and (avatar_file.filename or "").strip():
        try:
            url, _, _ = process_and_save_image(avatar_file)
            s.avatar_url = url
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("dashboard.staff_manage"))
    db.session.add(s)
    db.session.commit()
    flash("Staff member updated", "success")
    return redirect(url_for("dashboard.staff_manage"))


@dashboard_bp.route("/staff/<int:staff_id>/delete", methods=["POST"]) 
@login_required
def staff_delete(staff_id: int):
    r = _require_admin_restaurant()
    s = Staff.query.filter_by(id=staff_id, restaurant_id=r.id).first_or_404()
    s.active = False
    db.session.add(s)
    db.session.commit()
    flash("Staff member marked inactive", "info")
    return redirect(url_for("dashboard.staff_manage"))

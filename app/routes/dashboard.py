from __future__ import annotations

from datetime import datetime, timedelta, date
from collections import defaultdict

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response
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
)
from ..services.image_service import process_and_save_image


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


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


def _sum_tips_q(q):
    total = 0
    for t in q:
        total += int(t.amount_cents or 0)
    return total


@dashboard_bp.route("/restaurant")
@login_required
def restaurant_view():
    r = _require_admin_restaurant()

    now = datetime.utcnow()
    start_today = datetime(now.year, now.month, now.day)
    start_week = start_today - timedelta(days=start_today.weekday())
    start_month = datetime(now.year, now.month, 1)

    tips_today = _sum_tips_q(Tip.query.filter_by(restaurant_id=r.id).filter(Tip.created_at >= start_today).all())
    tips_week = _sum_tips_q(Tip.query.filter_by(restaurant_id=r.id).filter(Tip.created_at >= start_week).all())
    tips_month = _sum_tips_q(Tip.query.filter_by(restaurant_id=r.id).filter(Tip.created_at >= start_month).all())

    reviews_q = Review.query.filter_by(restaurant_id=r.id).all()
    rating_avg = (sum(rv.rating for rv in reviews_q) / len(reviews_q)) if reviews_q else 0.0
    reviews_count = len(reviews_q)

    # Top 3 by tips
    totals_by_staff: dict[int, int] = defaultdict(int)
    for t in Tip.query.filter_by(restaurant_id=r.id).all():
        if t.staff_id:
            totals_by_staff[t.staff_id] += int(t.amount_cents or 0)
    staff_objs = {s.id: s for s in Staff.query.filter_by(restaurant_id=r.id).all()}
    top_tipped = sorted(((staff_objs.get(sid), total) for sid, total in totals_by_staff.items() if staff_objs.get(sid)), key=lambda x: x[1], reverse=True)[:3]

    # Top 3 by rating
    top_rated = Staff.query.filter_by(restaurant_id=r.id, active=True).order_by(Staff.rating_avg.desc()).limit(3).all()

    # Staff cards with pending amounts (mock: tips total - sent transfers)
    sent_by_staff: dict[int, int] = defaultdict(int)
    for tr in Transfer.query.filter_by(restaurant_id=r.id).all():
        if tr.staff_id:
            sent_by_staff[tr.staff_id] += int(tr.amount_cents or 0)
    staff_cards = []
    staff_all = Staff.query.filter_by(restaurant_id=r.id, active=True).order_by(Staff.name.asc()).all()
    for s in staff_all:
        pending = totals_by_staff.get(s.id, 0) - sent_by_staff.get(s.id, 0)
        staff_cards.append((s, max(0, pending)))

    # Charts data: current month vs previous month daily totals
    def _daily_totals_for_month(year: int, month: int):
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)
        days = (end - start).days
        totals = [0] * days
        rows = Tip.query.filter_by(restaurant_id=r.id).filter(Tip.created_at >= start, Tip.created_at < end).all()
        for t in rows:
            idx = (t.created_at.date() - start.date()).days
            if 0 <= idx < days:
                totals[idx] += int(t.amount_cents or 0)
        labels = [str(d + 1) for d in range(days)]
        return labels, totals

    curr_labels, daily_current = _daily_totals_for_month(now.year, now.month)
    prev_year, prev_month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    prev_labels, daily_previous = _daily_totals_for_month(prev_year, prev_month)
    # Align label lengths for template simplicity
    daily_previous = (daily_previous + [0] * max(0, len(curr_labels) - len(daily_previous)))[: len(curr_labels)]

    staff_labels = [s.name for s in staff_all]
    staff_totals = [totals_by_staff.get(s.id, 0) for s in staff_all]

    recent_reviews = Review.query.filter_by(restaurant_id=r.id).order_by(Review.created_at.desc()).limit(10).all()

    return render_template(
        "dashboard/restaurant.html",
        restaurant=r,
        tips_today=tips_today,
        tips_week=tips_week,
        tips_month=tips_month,
        rating_avg=rating_avg,
        reviews_count=reviews_count,
        top_tipped=top_tipped,
        top_rated=top_rated,
        staff_cards=staff_cards,
        daily_labels=curr_labels,
        daily_current=daily_current,
        daily_previous=daily_previous,
        staff_labels=staff_labels,
        staff_totals=staff_totals,
        recent_reviews=recent_reviews,
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


@dashboard_bp.route("/staff/<int:staff_id>")
@login_required
def staff_view(staff_id: int):
    r = _require_admin_restaurant()
    s = Staff.query.filter_by(id=staff_id, restaurant_id=r.id).first_or_404()
    now = datetime.utcnow()
    start_today = datetime(now.year, now.month, now.day)
    start_week = start_today - timedelta(days=start_today.weekday())
    tips_today = _sum_tips_q(Tip.query.filter_by(restaurant_id=r.id, staff_id=s.id).filter(Tip.created_at >= start_today).all())
    tips_week = _sum_tips_q(Tip.query.filter_by(restaurant_id=r.id, staff_id=s.id).filter(Tip.created_at >= start_week).all())
    rating_vals = [rv.rating for rv in Review.query.filter_by(restaurant_id=r.id, staff_id=s.id).all()]
    rating_avg = (sum(rating_vals) / len(rating_vals)) if rating_vals else 0.0
    last_tips = Tip.query.filter_by(restaurant_id=r.id, staff_id=s.id).order_by(Tip.created_at.desc()).limit(10).all()
    last_reviews = Review.query.filter_by(restaurant_id=r.id, staff_id=s.id).order_by(Review.created_at.desc()).limit(10).all()
    return render_template("dashboard/staff.html", restaurant=r, staff=s, tips_today=tips_today, tips_week=tips_week, rating_avg=rating_avg, last_tips=last_tips, last_reviews=last_reviews)


@dashboard_bp.route("/staff/manage")
@login_required
def staff_manage():
    r = _require_admin_restaurant()
    staff_list = Staff.query.filter_by(restaurant_id=r.id).order_by(Staff.name.asc()).all()
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

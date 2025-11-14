from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, make_response
from flask_login import current_user
from ..extensions import db, limiter
from ..models import Restaurant, Staff, Tip, Review
from ..forms import TipForm, ReviewForm
from ..services.tip_service import create_tip
from ..services.review_service import create_review
from ..utils import device as device_util


public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def home():
    # Redirect to the first available restaurant, or show a quick help message
    r = Restaurant.query.order_by(Restaurant.id.asc()).first()
    if r:
        return redirect(url_for("public.tip_page", restaurant_slug=r.slug))
    return (
        "No restaurants configured. Run: python -m app.seed",
        200,
    )


def _get_restaurant_or_404(slug: str) -> Restaurant:
    r = Restaurant.query.filter_by(slug=slug).first()
    if not r:
        abort(404)
    return r


@public_bp.route("/r/<restaurant_slug>", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def tip_page(restaurant_slug):
    restaurant = _get_restaurant_or_404(restaurant_slug)
    staff_list = Staff.query.filter_by(restaurant_id=restaurant.id, active=True).order_by(Staff.name.asc()).all()
    form = TipForm()
    if request.method == "GET":
        form.restaurant_id.data = restaurant.id
        form.method_ui.data = form.method_ui.choices[0][0]
    if form.validate_on_submit():
        if int(form.restaurant_id.data) != restaurant.id:
            abort(400)
        staff_id = int(form.staff_id.data) if form.staff_id.data else None
        user = current_user if current_user.is_authenticated else device_util.get_or_create_guest_user()
        tip = create_tip(restaurant.id, staff_id, user, form.amount_cents.data, form.method_ui.data)
        resp = make_response(redirect(url_for("public.feedback_page", restaurant_slug=restaurant.slug, tip=tip.id)))
        device_util.ensure_device_cookie(resp)
        flash("Tip recorded. Thank you!", "success")
        return resp
    return render_template("public/tip.html", restaurant=restaurant, staff_list=staff_list, form=form)


@public_bp.route("/r/<restaurant_slug>/feedback", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def feedback_page(restaurant_slug):
    restaurant = _get_restaurant_or_404(restaurant_slug)
    tip_id = request.args.get("tip", type=int)
    tip = Tip.query.filter_by(id=tip_id, restaurant_id=restaurant.id).first() if tip_id else None
    staff = Staff.query.get(tip.staff_id) if tip and tip.staff_id else None
    form = ReviewForm()
    if form.validate_on_submit():
        user = current_user if current_user.is_authenticated else device_util.get_or_create_guest_user()
        photo = request.files.get("photo")
        try:
            review = create_review(restaurant.id, staff, user, form.rating.data, form.comment.data, form.share_allowed.data, photo)
        except ValueError as e:
            flash(str(e), "danger")
            return render_template("public/feedback.html", restaurant=restaurant, tip=tip, staff=staff, form=form)
        resp = make_response(redirect(url_for("public.thanks_page", restaurant_slug=restaurant.slug, tip=tip.id if tip else None)))
        device_util.ensure_device_cookie(resp)
        flash("Feedback sent!", "success")
        return resp
    return render_template("public/feedback.html", restaurant=restaurant, tip=tip, staff=staff, form=form)


@public_bp.route("/r/<restaurant_slug>/thanks")
def thanks_page(restaurant_slug):
    restaurant = _get_restaurant_or_404(restaurant_slug)
    tip_id = request.args.get("tip", type=int)
    tip = Tip.query.filter_by(id=tip_id, restaurant_id=restaurant.id).first() if tip_id else None
    staff = Staff.query.get(tip.staff_id) if tip and tip.staff_id else None
    last_review = Review.query.filter_by(restaurant_id=restaurant.id, user_id=(current_user.id if current_user.is_authenticated else None)).order_by(Review.created_at.desc()).first()
    user = current_user if current_user.is_authenticated else None
    from ..models import RewardTier
    tiers = RewardTier.query.order_by(RewardTier.threshold_xp.asc()).all()
    xp = user.xp if user else 0
    next_tier = None
    for t in tiers:
        if xp < t.threshold_xp:
            next_tier = t
            break
    current_level = user.level if user else 1
    progress_pct = 100
    if next_tier:
        prev_thresh = 0
        for t in tiers:
            if (user.xp if user else 0) >= t.threshold_xp:
                prev_thresh = t.threshold_xp
            else:
                break
        span = max(1, next_tier.threshold_xp - prev_thresh)
        progress_pct = int(100 * ((xp - prev_thresh) / span))
    return render_template("public/thanks.html", restaurant=restaurant, staff=staff, tip=tip, user=user, current_level=current_level, next_tier=next_tier, progress_pct=progress_pct)

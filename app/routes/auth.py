from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required, logout_user

from ..forms import LoginForm, RegisterForm
from ..services.auth_service import authenticate, register_user
from ..services.merge_service import merge_guest_into_user
from ..utils import device as device_util
from ..extensions import db
from ..models import User, Restaurant, Tip, Review, RewardTier, Coupon


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        try:
            authenticate(form.email.data, form.password.data)
            flash("Bienvenido", "success")
            next_url = request.args.get("next") or url_for("auth.profile")
            return redirect(next_url)
        except ValueError as e:
            flash(str(e), "danger")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            register_user(form.email.data, form.password.data, form.name.data)
            flash("Cuenta creada", "success")
            return redirect(url_for("auth.profile"))
        except ValueError as e:
            flash(str(e), "danger")
    return render_template("auth/register.html", form=form)


@auth_bp.route("/logout", methods=["POST"]) 
@login_required
def logout():
    logout_user()
    flash("Sesion cerrada", "info")
    return redirect(url_for("public.home"))


@auth_bp.route("/me/profile")
def profile():
    # Usa usuario autenticado o crea/recupera invitado por cookie de dispositivo
    user = current_user if current_user.is_authenticated else device_util.get_or_create_guest_user()

    tips = (
        Tip.query.filter_by(user_id=user.id).order_by(Tip.created_at.desc()).limit(20).all()
    )
    reviews = (
        Review.query.filter_by(user_id=user.id).order_by(Review.created_at.desc()).limit(20).all()
    )

    restaurant_ids = {t.restaurant_id for t in tips} | {r.restaurant_id for r in reviews}
    restaurants = (
        Restaurant.query.filter(Restaurant.id.in_(restaurant_ids)).order_by(Restaurant.name.asc()).all()
        if restaurant_ids
        else []
    )

    # Calcular siguiente nivel y progreso (si hay RewardTiers)
    tiers = RewardTier.query.order_by(RewardTier.threshold_xp.asc()).all()
    xp = user.xp or 0
    next_tier = None
    progress_pct = 100
    if tiers:
        prev_thresh = 0
        for t in tiers:
            if xp >= t.threshold_xp:
                prev_thresh = t.threshold_xp
            else:
                next_tier = t
                break
        if next_tier:
            span = max(1, next_tier.threshold_xp - prev_thresh)
            progress_pct = int(100 * ((xp - prev_thresh) / span))

    # Cupones desbloqueados por restaurante (requisito XP <= user.xp)
    unlocked_by_rest = {}
    if restaurants:
        for r in restaurants:
            cs = (
                Coupon.query.filter_by(restaurant_id=r.id, active=True)
                .filter(Coupon.required_xp <= xp)
                .order_by(Coupon.required_xp.asc())
                .all()
            )
            if cs:
                unlocked_by_rest[r.id] = {"restaurant": r, "coupons": cs}

    return render_template(
        "auth/profile.html",
        user=user,
        restaurants=restaurants,
        tips=tips,
        reviews=reviews,
        next_tier=next_tier,
        progress_pct=progress_pct,
        unlocked_by_rest=unlocked_by_rest,
    )


@auth_bp.route("/me/merge-guest", methods=["POST"])
@login_required
def merge_guest():
    did = device_util.get_device_id()
    if not did:
        flash("No hay datos de dispositivo a fusionar", "info")
        return redirect(url_for("auth.profile"))
    dh = device_util.device_hash(did)
    guest = User.query.filter_by(device_id_hash=dh).first()
    if not guest or guest.id == current_user.id:
        flash("No hay actividad anonima para fusionar", "info")
        return redirect(url_for("auth.profile"))
    merge_guest_into_user(guest, current_user)
    flash("Perfil anonimo fusionado", "success")
    return redirect(url_for("auth.profile"))

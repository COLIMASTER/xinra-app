from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required, logout_user
from datetime import datetime, timedelta

from ..forms import LoginForm, RegisterForm
from ..services.auth_service import authenticate, register_user
from ..services.merge_service import merge_guest_into_user
from ..utils import device as device_util
from ..extensions import db
from ..models import User, Restaurant, Tip, Review, RewardTier, Coupon, CouponRedemption, Staff


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
    # Datos completos para logros y misión
    all_tips = Tip.query.filter_by(user_id=user.id).all()
    all_reviews = Review.query.filter_by(user_id=user.id).all()

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

    # Cupones: disponibles para reclamar (no reclamados) y reclamados
    available_by_rest = {}
    claimed_by_rest = {}
    if restaurants:
        # Redenciones del usuario
        redemptions = CouponRedemption.query.filter_by(user_id=user.id).all()
        claimed_ids = {cr.coupon_id for cr in redemptions}
        by_rest_claimed = {}
        for cr in redemptions:
            if not cr.coupon:
                continue
            lst = by_rest_claimed.setdefault(cr.coupon.restaurant_id, [])
            lst.append(cr)

        for r in restaurants:
            # disponibles con requisito XP cumplido y activos, excluyendo ya reclamados
            q = (
                Coupon.query.filter_by(restaurant_id=r.id, active=True)
                .filter(Coupon.required_xp <= xp)
            )
            if claimed_ids:
                q = q.filter(~Coupon.id.in_(claimed_ids))
            available = q.order_by(Coupon.required_xp.asc()).all()
            if available:
                available_by_rest[r.id] = {"restaurant": r, "coupons": available}
            claimed_list = by_rest_claimed.get(r.id)
            if claimed_list:
                claimed_by_rest[r.id] = {"restaurant": r, "redemptions": claimed_list}

    return render_template(
        "auth/profile.html",
        user=user,
        restaurants=restaurants,
        tips=tips,
        reviews=reviews,
        next_tier=next_tier,
        progress_pct=progress_pct,
        available_by_rest=available_by_rest,
        claimed_by_rest=claimed_by_rest,
        achievements=_compute_achievements(user, all_tips, all_reviews),
        mission=_compute_weekly_mission(user),
    )


def _gen_coupon_code(n: int = 10) -> str:
    import secrets, string
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))


@auth_bp.route("/me/coupons/<int:coupon_id>/claim", methods=["POST"]) 
def claim_coupon(coupon_id: int):
    # Permitir invitado (usuario creado por dispositivo)
    user = current_user if current_user.is_authenticated else device_util.get_or_create_guest_user()
    c = Coupon.query.filter_by(id=coupon_id, active=True).first()
    if not c:
        flash("Cupón no disponible", "danger")
        return redirect(url_for("auth.profile"))
    if (user.xp or 0) < int(c.required_xp or 0):
        flash("Aún no alcanzas el XP requerido", "danger")
        return redirect(url_for("auth.profile"))
    exists = CouponRedemption.query.filter_by(coupon_id=c.id, user_id=user.id).first()
    if exists:
        flash("Este cupón ya fue reclamado", "info")
        return redirect(url_for("auth.profile"))

    code = _gen_coupon_code(10)
    tries = 0
    while CouponRedemption.query.filter_by(code=code).first() and tries < 5:
        code = _gen_coupon_code(10)
        tries += 1

    cr = CouponRedemption(coupon_id=c.id, user_id=user.id, code=code, status="claimed")
    db.session.add(cr)
    db.session.commit()
    flash("Cupón reclamado", "success")
    return redirect(url_for("auth.profile"))


# ---- Helper: achievements & mission ----
def _compute_achievements(user: User, all_tips: list[Tip], all_reviews: list[Review]):
    # Explorador de cafés: 3+ restaurantes distintos
    rest_ids = {t.restaurant_id for t in all_tips} | {r.restaurant_id for r in all_reviews}
    explorer = len([rid for rid in rest_ids if rid]) >= 3

    # Fan del latte art: 5+ propinas a baristas
    fan_latte = False
    if all_tips:
        staff_ids = {t.staff_id for t in all_tips if t.staff_id}
        roles = {}
        if staff_ids:
            for s in Staff.query.filter(Staff.id.in_(staff_ids)).all():
                roles[s.id] = (s.role or '').lower()
        barista_tips = sum(1 for t in all_tips if t.staff_id and 'barista' in (roles.get(t.staff_id, '')))
        fan_latte = barista_tips >= 5

    # Crítico amable: 5+ reseñas con 4★ o más
    critic = sum(1 for r in all_reviews if (r.rating or 0) >= 4) >= 5

    return [
        {'key': 'explorer', 'name': 'Explorador de cafés', 'earned': explorer, 'desc': 'Visita 3+ cafeterías diferentes'},
        {'key': 'latte_fan', 'name': 'Fan del latte art', 'earned': fan_latte, 'desc': '5+ propinas a baristas'},
        {'key': 'kind_critic', 'name': 'Crítico amable', 'earned': critic, 'desc': '5+ reseñas con 4★ o más'},
    ]


def _compute_weekly_mission(user: User):
    # Misión: 3 propinas esta semana
    now = datetime.utcnow()
    start_week = now - timedelta(days=now.weekday())
    start_week = datetime(start_week.year, start_week.month, start_week.day)
    count = Tip.query.filter_by(user_id=user.id).filter(Tip.created_at >= start_week).count()
    goal = 3
    return {
        'title': 'Da 3 propinas esta semana',
        'progress': min(count, goal),
        'goal': goal,
        'completed': count >= goal,
        'start': start_week,
    }


@auth_bp.route("/me/summary")
def summary():
    user = current_user if current_user.is_authenticated else device_util.get_or_create_guest_user()
    tips = Tip.query.filter_by(user_id=user.id).order_by(Tip.created_at.asc()).all()
    reviews = Review.query.filter_by(user_id=user.id).all()

    total_count = len(tips)
    total_cents = sum(int(t.amount_cents or 0) for t in tips)
    avg_cents = int(total_cents / total_count) if total_count else 0

    # Top restaurantes por monto
    by_rest = {}
    for t in tips:
        by_rest.setdefault(t.restaurant_id, 0)
        by_rest[t.restaurant_id] += int(t.amount_cents or 0)
    top_rest = []
    if by_rest:
        rest_map = {r.id: r for r in Restaurant.query.filter(Restaurant.id.in_(by_rest.keys())).all()}
        top_rest = sorted(((rest_map.get(rid), amt) for rid, amt in by_rest.items() if rest_map.get(rid)), key=lambda x: x[1], reverse=True)[:5]

    # Métodos más usados
    by_method = {}
    for t in tips:
        key = t.method_ui or 'otro'
        by_method[key] = by_method.get(key, 0) + 1

    # Línea de tiempo mensual (últimos 12 meses)
    timeline = []
    if tips:
        end = datetime.utcnow().replace(day=1)
        months = []
        y, m = end.year, end.month
        for _ in range(12):
            months.append((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        months = list(reversed(months))
        for (y, m) in months:
            start = datetime(y, m, 1)
            nxt = datetime(y+1, 1, 1) if m == 12 else datetime(y, m+1, 1)
            amt = sum(int(t.amount_cents or 0) for t in tips if start <= t.created_at < nxt)
            timeline.append({'label': f"{y}-{m:02d}", 'amount_cents': amt})

    return render_template(
        "auth/summary.html",
        user=user,
        total_count=total_count,
        total_cents=total_cents,
        avg_cents=avg_cents,
        top_rest=top_rest,
        by_method=by_method,
        timeline=timeline,
        reviews_count=len(reviews),
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

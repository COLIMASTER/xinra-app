from datetime import datetime
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import JSON
from .extensions import db, login_manager


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    name = db.Column(db.String(120), nullable=True)
    avatar_url = db.Column(db.String(512), nullable=True)
    device_id_hash = db.Column(db.String(64), unique=True, nullable=True)
    level = db.Column(db.Integer, default=1, nullable=False)
    xp = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    memberships = db.relationship("Membership", backref="user", lazy=True)
    tips = db.relationship("Tip", backref="user", lazy=True)
    reviews = db.relationship("Review", backref="user", lazy=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Restaurant(db.Model):
    __tablename__ = "restaurants"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    logo_url = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    staff = db.relationship("Staff", backref="restaurant", lazy=True)
    tips = db.relationship("Tip", backref="restaurant", lazy=True)
    reviews = db.relationship("Review", backref="restaurant", lazy=True)


class Staff(db.Model):
    __tablename__ = "staff"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(120), nullable=True)
    avatar_url = db.Column(db.String(512), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    rating_avg = db.Column(db.Float, default=0.0, nullable=False)
    tips_count = db.Column(db.Integer, default=0, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    login_initial_password = db.Column(db.String(64), nullable=True)

    tips = db.relationship("Tip", backref="staff", lazy=True)
    reviews = db.relationship("Review", backref="staff", lazy=True)
    user = db.relationship("User", backref=db.backref("staff", uselist=False))


class Membership(db.Model):
    __tablename__ = "memberships"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    role = db.Column(db.String(50), default="user", nullable=False)

    restaurant = db.relationship("Restaurant", backref=db.backref("memberships", lazy=True))

    __table_args__ = (
        db.Index("ix_memberships_restaurant_id", "restaurant_id"),
    )


class Tip(db.Model):
    __tablename__ = "tips"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    amount_cents = db.Column(db.Integer, nullable=False)
    method_ui = db.Column(db.Text, default="mock", nullable=False)
    status = db.Column(db.Text, default="recorded", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.Index("ix_tips_restaurant_created", "restaurant_id", "created_at"),
    )


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    share_allowed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    media = db.relationship("Media", backref="review", uselist=False, lazy=True)

    __table_args__ = (
        db.Index("ix_reviews_restaurant_created", "restaurant_id", "created_at"),
    )


class Media(db.Model):
    __tablename__ = "media"
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey("reviews.id"), nullable=False)
    url = db.Column(db.Text, nullable=False)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)


class ImageAsset(db.Model):
    __tablename__ = "image_assets"
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), unique=True, nullable=False)
    content_type = db.Column(db.String(50), nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class RewardTier(db.Model):
    __tablename__ = "reward_tiers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    threshold_xp = db.Column(db.Integer, nullable=False)
    perks_json = db.Column(JSON, nullable=True)


class UserReward(db.Model):
    __tablename__ = "user_rewards"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reward_id = db.Column(db.Integer, db.ForeignKey("reward_tiers.id"), nullable=False)
    status = db.Column(db.Text, default="unlocked", nullable=False)
    claimed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref=db.backref("user_rewards", lazy=True))
    reward = db.relationship("RewardTier", backref=db.backref("user_rewards", lazy=True))


class PayoutAccount(db.Model):
    __tablename__ = "payout_accounts"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    provider = db.Column(db.String(50), nullable=False)
    external_id = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), default="unlinked", nullable=False)

    restaurant = db.relationship("Restaurant", backref=db.backref("payout_accounts", lazy=True))


class Transfer(db.Model):
    __tablename__ = "transfers"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=True)
    amount_cents = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default="pending", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    restaurant = db.relationship("Restaurant")
    staff_ref = db.relationship("Staff")


class Coupon(db.Model):
    __tablename__ = "coupons"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    required_xp = db.Column(db.Integer, default=0, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    restaurant = db.relationship("Restaurant", backref=db.backref("coupons", lazy=True))

    __table_args__ = (
        db.Index("ix_coupons_restaurant_active", "restaurant_id", "active"),
    )


class CouponRedemption(db.Model):
    __tablename__ = "coupon_redemptions"
    id = db.Column(db.Integer, primary_key=True)
    coupon_id = db.Column(db.Integer, db.ForeignKey("coupons.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    code = db.Column(db.String(24), unique=True, nullable=False)
    status = db.Column(db.String(20), default="claimed", nullable=False)  # claimed|used|expired
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    coupon = db.relationship("Coupon", backref=db.backref("redemptions", lazy=True))
    user = db.relationship("User", backref=db.backref("coupon_redemptions", lazy=True))

    __table_args__ = (
        db.Index("ix_redemptions_user", "user_id"),
        db.Index("ix_redemptions_coupon", "coupon_id"),
    )

import random
from datetime import datetime, timedelta
from flask import Flask
from . import create_app
from .extensions import db
from .models import Restaurant, Staff, User, Membership, Tip, Review, RewardTier, Coupon
from .utils.security import hash_password


def run_seed():
    app: Flask = create_app()
    with app.app_context():
        db.create_all()

        if not RewardTier.query.first():
            db.session.add_all([
                RewardTier(name="Bronze", threshold_xp=0),
                RewardTier(name="Silver", threshold_xp=100),
                RewardTier(name="Gold", threshold_xp=250),
                RewardTier(name="Platinum", threshold_xp=500),
                RewardTier(name="Diamond", threshold_xp=1000),
                RewardTier(name="Master", threshold_xp=2000),
            ])

        r = Restaurant.query.filter_by(slug="cafe-luna").first()
        if not r:
            r = Restaurant(slug="cafe-luna", name="Cafe Luna", logo_url="https://placehold.co/200x80?text=Cafe+Luna")
            db.session.add(r)
            db.session.flush()

        staff = Staff.query.filter_by(restaurant_id=r.id).all()
        if not staff:
            staff = [
                Staff(restaurant_id=r.id, name="Mia", role="Barista", avatar_url="https://placehold.co/96x96?text=M", bio="Latte art specialist and single-origin coffee lover."),
                Staff(restaurant_id=r.id, name="Jake", role="Barista", avatar_url="https://placehold.co/96x96?text=J", bio="Espresso perfectionist; try his cappuccino."),
                Staff(restaurant_id=r.id, name="Tess", role="Server", avatar_url="https://placehold.co/96x96?text=T", bio="Always smiling; she’ll make your visit delightful."),
                Staff(restaurant_id=r.id, name="Leo", role="Cook", avatar_url="https://placehold.co/96x96?text=L", bio="Creative chef; responsible for daily specials."),
            ]
            db.session.add_all(staff)

        admin = User.query.filter_by(email="admin@demo.com").first()
        if not admin:
            admin = User(email="admin@demo.com", name="Admin", password_hash=hash_password("demo123"), level=1, xp=0)
            db.session.add(admin)
            db.session.flush()
            db.session.add(Membership(user_id=admin.id, restaurant_id=r.id, role="admin"))

        mia_user = User.query.filter_by(email="mia@demo.com").first()
        if not mia_user:
            mia_user = User(email="mia@demo.com", name="Mia", password_hash=hash_password("demo123"), level=1, xp=0)
            db.session.add(mia_user)
            db.session.flush()
            db.session.add(Membership(user_id=mia_user.id, restaurant_id=r.id, role="staff"))

        db.session.commit()

        since = datetime.utcnow() - timedelta(days=7)
        tips_count = Tip.query.filter_by(restaurant_id=r.id).count()
        if tips_count < 20:
            for _ in range(20):
                s = random.choice(staff)
                amount = random.choice([200, 300, 500, 700, 1000])
                t = Tip(restaurant_id=r.id, staff_id=s.id, user_id=None, amount_cents=amount, method_ui=random.choice(["apple_pay", "google_pay", "paypal"]), status="recorded", created_at=since + timedelta(days=random.randint(0, 6), hours=random.randint(0, 23)))
                db.session.add(t)

        reviews_count = Review.query.filter_by(restaurant_id=r.id).count()
        if reviews_count < 10:
            for _ in range(10):
                s = random.choice(staff)
                rating = random.randint(4, 5)
                rv = Review(restaurant_id=r.id, staff_id=s.id, user_id=None, rating=rating, comment=random.choice(["Excellent", "Very good", "Great coffee", "Friendly service"]))
                db.session.add(rv)

        db.session.commit()

        # Seed coupons for the demo restaurant
        if not Coupon.query.filter_by(restaurant_id=r.id).first():
            db.session.add_all([
                Coupon(restaurant_id=r.id, title="Free Coffee", description="1 free drink (small)", required_xp=100, active=True),
                Coupon(restaurant_id=r.id, title="2-for-1 Latte", description="Valid Mon–Thu", required_xp=250, active=True),
                Coupon(restaurant_id=r.id, title="Free Merch", description="Limited edition tote bag", required_xp=500, active=True),
            ])
            db.session.commit()

        for s in staff:
            s.tips_count = len(s.tips)
            if s.reviews:
                s.rating_avg = sum([rv.rating for rv in s.reviews]) / len(s.reviews)
        db.session.commit()

        print("Seed complete: Cafe Luna available at /r/cafe-luna")


if __name__ == "__main__":
    run_seed()

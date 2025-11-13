from statistics import mean
from ..extensions import db
from ..models import Review, Media, Staff, User
from .image_service import process_and_save_image
from .reward_service import add_xp


def create_review(restaurant_id: int, staff: Staff | None, user: User | None, rating: int, comment: str | None, share_allowed: bool, file_storage) -> Review:
    review = Review(restaurant_id=restaurant_id, staff_id=staff.id if staff else None, user_id=user.id if user else None, rating=rating, comment=comment or None, share_allowed=share_allowed)
    db.session.add(review)
    photo_saved = False
    if file_storage and getattr(file_storage, "filename", None):
        url, width, height = process_and_save_image(file_storage)
        media = Media(review=review, url=url, width=width, height=height)
        db.session.add(media)
        photo_saved = True

    if user:
        gained = (5 if (comment and comment.strip()) else 0) + (5 if photo_saved else 0)
        if gained:
            add_xp(user, gained)

    db.session.flush()

    if staff:
        staff_reviews = [r.rating for r in staff.reviews]
        staff.rating_avg = mean(staff_reviews) if staff_reviews else 0
        staff.tips_count = len(staff.tips)

    db.session.commit()
    return review

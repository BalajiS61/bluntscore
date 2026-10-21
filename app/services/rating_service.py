"""Create, update and delete user star ratings (one rating per user per topic)."""
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import Topic, UserRating


def upsert_rating(
    db: Session, topic: Topic, user_id: str, rating: int, comment: Optional[str]
) -> Tuple[UserRating, bool]:
    """Returns (rating, created). Rating again as the same user updates the old rating."""
    existing = db.scalar(
        select(UserRating).where(UserRating.topic_id == topic.id, UserRating.user_id == user_id)
    )
    if existing is not None:
        existing.rating = rating
        existing.comment = comment
        db.commit()
        return existing, False

    new = UserRating(topic=topic, user_id=user_id, rating=rating, comment=comment)
    db.add(new)
    db.commit()
    return new, True


def delete_rating(db: Session, topic: Topic, user_id: str) -> None:
    existing = db.scalar(
        select(UserRating).where(UserRating.topic_id == topic.id, UserRating.user_id == user_id.strip())
    )
    if existing is None:
        raise NotFoundError(f"User '{user_id}' has not rated '{topic.slug}'")
    db.delete(existing)
    db.commit()


def list_ratings(db: Session, topic: Topic, limit: int = 20, offset: int = 0) -> List[UserRating]:
    return list(
        db.scalars(
            select(UserRating)
            .where(UserRating.topic_id == topic.id)
            .order_by(UserRating.updated_at.desc(), UserRating.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )

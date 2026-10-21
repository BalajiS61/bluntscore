"""UserRating: an explicit 1-5 star rating a user gives a topic."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.topic import Topic


class UserRating(TimestampMixin, Base):
    __tablename__ = "user_ratings"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(80), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text)

    topic: Mapped["Topic"] = relationship(back_populates="ratings")

    __table_args__ = (
        UniqueConstraint("topic_id", "user_id", name="uq_rating_topic_user"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_rating_range"),
    )

    def __repr__(self) -> str:
        return f"<UserRating topic_id={self.topic_id} user={self.user_id!r} rating={self.rating}>"

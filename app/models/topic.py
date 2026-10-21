"""Topic: anything people can search for and get a BluntScore on."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.database import Base
from app.models.mixins import TimestampMixin
from app.utils.text import slugify

if TYPE_CHECKING:
    from app.models.review import Review
    from app.models.user_rating import UserRating


class Topic(TimestampMixin, Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(60), index=True)

    # Cached aggregates, recomputed by the scoring engine (Step 4)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    positive_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    neutral_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    negative_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    reviews: Mapped[List["Review"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )
    ratings: Mapped[List["UserRating"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(
            "sentiment_score IS NULL OR (sentiment_score >= 0 AND sentiment_score <= 100)",
            name="ck_topic_score_range",
        ),
    )

    @validates("name")
    def _set_name_and_slug(self, _key: str, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("Topic name cannot be empty")
        self.slug = slugify(value)
        return value

    def __repr__(self) -> str:
        return f"<Topic id={self.id} slug={self.slug!r} score={self.sentiment_score}>"

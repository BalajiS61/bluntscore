"""Review: one opinion about a topic from one source, plus its NLP result."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.database import Base
from app.models.enums import SentimentLabel, enum_column
from app.models.mixins import TimestampMixin, UTCDateTime
from app.utils.text import content_hash

if TYPE_CHECKING:
    from app.models.source import Source
    from app.models.topic import Topic


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True, nullable=False
    )

    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(120))
    external_id: Mapped[Optional[str]] = mapped_column(String(120))
    published_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())

    # Filled in by the NLP engine (Step 3)
    sentiment_label: Mapped[Optional[SentimentLabel]] = mapped_column(enum_column(SentimentLabel))
    sentiment_compound: Mapped[Optional[float]] = mapped_column(Float)    # -1.0 .. 1.0
    sentiment_confidence: Mapped[Optional[float]] = mapped_column(Float)  #  0.0 .. 1.0
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())

    topic: Mapped["Topic"] = relationship(back_populates="reviews")
    source: Mapped["Source"] = relationship(back_populates="reviews")

    __table_args__ = (
        UniqueConstraint("topic_id", "content_hash", name="uq_review_topic_hash"),
        UniqueConstraint("source_id", "external_id", name="uq_review_source_external"),
        CheckConstraint(
            "sentiment_compound IS NULL OR (sentiment_compound >= -1 AND sentiment_compound <= 1)",
            name="ck_review_compound_range",
        ),
        CheckConstraint(
            "sentiment_confidence IS NULL OR (sentiment_confidence >= 0 AND sentiment_confidence <= 1)",
            name="ck_review_confidence_range",
        ),
        Index("ix_review_topic_label", "topic_id", "sentiment_label"),
    )

    @validates("text")
    def _set_text_and_hash(self, _key: str, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("Review text cannot be empty")
        self.content_hash = content_hash(value)
        return value

    def __repr__(self) -> str:
        return f"<Review id={self.id} topic_id={self.topic_id} label={self.sentiment_label}>"

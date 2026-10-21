"""Source: where reviews come from (Amazon, Reddit, news, a CSV upload...)."""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, CheckConstraint, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import SourceType, enum_column
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.review import Review


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        enum_column(SourceType), default=SourceType.OTHER, nullable=False
    )
    # Reliability weight used by the scoring engine: 1.0 = normal, >1 trusted, <1 noisy
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    reviews: Mapped[List["Review"]] = relationship(
        back_populates="source", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("weight > 0 AND weight <= 5", name="ck_source_weight_range"),
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id} name={self.name!r} weight={self.weight}>"

"""Source request/response models."""
from typing import Annotated, Optional

from pydantic import BaseModel, Field, StringConstraints

from app.models import Source
from app.models.enums import SourceType


class SourceOut(BaseModel):
    id: int
    name: str
    source_type: SourceType
    weight: float
    description: Optional[str]
    is_active: bool
    review_count: int

    @classmethod
    def build(cls, source: Source, review_count: int) -> "SourceOut":
        return cls(
            id=source.id,
            name=source.name,
            source_type=source.source_type,
            weight=source.weight,
            description=source.description,
            is_active=source.is_active,
            review_count=review_count,
        )


class SourceUpdate(BaseModel):
    weight: Optional[float] = Field(default=None, gt=0, le=5, examples=[1.5])
    is_active: Optional[bool] = None
    source_type: Optional[SourceType] = None
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None


class SourceUpdateOut(BaseModel):
    source: SourceOut
    rescored_topics: int

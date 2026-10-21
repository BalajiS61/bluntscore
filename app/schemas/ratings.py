"""User rating request/response models."""
from datetime import datetime
from typing import Annotated, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

UserId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class RatingIn(BaseModel):
    user_id: UserId = Field(examples=["user_42"])
    rating: int = Field(ge=1, le=5, examples=[4])
    comment: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]] = None


class RatingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    rating: int
    comment: Optional[str]
    created_at: datetime
    updated_at: datetime


class RatingSubmitOut(BaseModel):
    created: bool
    rating: RatingOut
    topic_score: Optional[float]
    verdict: str


class RatingSummaryOut(BaseModel):
    topic_slug: str
    count: int
    average: Optional[float]
    distribution: Dict[str, int]
    items: List[RatingOut]

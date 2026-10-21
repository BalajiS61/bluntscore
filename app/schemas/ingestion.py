"""Request/response models for review ingestion."""
from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, StringConstraints

from app.models.enums import SourceType
from app.schemas.sentiment import ReviewText

TopicName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
SourceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]

MAX_REVIEWS_PER_REQUEST = 500


class ReviewIn(BaseModel):
    text: ReviewText
    author: Optional[ShortText] = None
    external_id: Optional[ShortText] = None
    published_at: Optional[datetime] = None


class IngestRequest(BaseModel):
    topic: TopicName = Field(examples=["Pixel 9"])
    category: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]] = None
    source: SourceName = Field(examples=["amazon"])
    source_type: SourceType = SourceType.OTHER
    reviews: List[ReviewIn] = Field(
        min_length=1,
        max_length=MAX_REVIEWS_PER_REQUEST,
        examples=[[
            {"text": "Amazing camera, love it!", "author": "arjun", "external_id": "amz-001"},
            {"text": "Battery drains too fast.", "published_at": "2026-10-01T09:30:00Z"},
        ]],
    )


class RowErrorOut(BaseModel):
    row: int
    message: str


class IngestionReportOut(BaseModel):
    topic_id: int
    topic_slug: str
    topic_name: str
    source: str
    received: int
    inserted: int
    duplicates: int
    rejected: int
    errors: List[RowErrorOut]
    sentiment_score: Optional[float]
    verdict: Optional[str]


class SampleTopicOut(BaseModel):
    topic_id: int
    topic_slug: str
    topic_name: str
    inserted_reviews: int
    inserted_ratings: int
    sentiment_score: Optional[float]
    verdict: str

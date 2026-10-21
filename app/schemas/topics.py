"""Topic, score, review and summary response models."""
from datetime import datetime
from typing import Annotated, Dict, List, Optional

from pydantic import BaseModel, Field, StringConstraints

from app.models import Review, Topic
from app.models.enums import SentimentLabel, SourceType
from app.scoring.engine import ScoreBreakdown, verdict_for

TopicName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Category = Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class TopicCreate(BaseModel):
    name: TopicName = Field(examples=["Galaxy S25"])
    category: Optional[Category] = Field(default=None, examples=["smartphones"])
    description: Optional[Description] = None


class TopicOut(BaseModel):
    id: int
    name: str
    slug: str
    category: Optional[str]
    description: Optional[str]
    sentiment_score: Optional[float]
    verdict: str
    review_count: int
    positive_count: int
    neutral_count: int
    negative_count: int
    last_scored_at: Optional[datetime]
    created_at: datetime

    @classmethod
    def from_topic(cls, topic: Topic) -> "TopicOut":
        return cls(
            id=topic.id,
            name=topic.name,
            slug=topic.slug,
            category=topic.category,
            description=topic.description,
            sentiment_score=topic.sentiment_score,
            verdict=verdict_for(topic.sentiment_score),
            review_count=topic.review_count,
            positive_count=topic.positive_count,
            neutral_count=topic.neutral_count,
            negative_count=topic.negative_count,
            last_scored_at=topic.last_scored_at,
            created_at=topic.created_at,
        )


class TopicDetailOut(TopicOut):
    rating_count: int
    average_rating: Optional[float]
    source_count: int


class ScoreOut(BaseModel):
    topic_slug: str
    topic_name: str
    score: Optional[float]
    verdict: str
    review_score: Optional[float]
    rating_score: Optional[float]
    average_rating: Optional[float]
    review_count: int
    rating_count: int
    positive_count: int
    neutral_count: int
    negative_count: int
    reliability: float
    last_scored_at: Optional[datetime]

    @classmethod
    def build(cls, topic: Topic, b: ScoreBreakdown) -> "ScoreOut":
        return cls(
            topic_slug=topic.slug,
            topic_name=topic.name,
            score=b.score,
            verdict=b.verdict,
            review_score=b.review_score,
            rating_score=b.rating_score,
            average_rating=b.average_rating,
            review_count=b.review_count,
            rating_count=b.rating_count,
            positive_count=b.positive_count,
            neutral_count=b.neutral_count,
            negative_count=b.negative_count,
            reliability=b.reliability,
            last_scored_at=topic.last_scored_at,
        )


class RefreshedTopic(BaseModel):
    slug: str
    name: str
    score: Optional[float]
    verdict: str


class RefreshAllOut(BaseModel):
    rescored: int
    topics: List[RefreshedTopic]


class ReviewOut(BaseModel):
    id: int
    text: str
    author: Optional[str]
    source: str
    sentiment_label: Optional[SentimentLabel]
    sentiment_compound: Optional[float]
    sentiment_confidence: Optional[float]
    published_at: Optional[datetime]
    created_at: datetime

    @classmethod
    def from_review(cls, review: Review) -> "ReviewOut":
        return cls(
            id=review.id,
            text=review.text,
            author=review.author,
            source=review.source.name,
            sentiment_label=review.sentiment_label,
            sentiment_compound=review.sentiment_compound,
            sentiment_confidence=review.sentiment_confidence,
            published_at=review.published_at,
            created_at=review.created_at,
        )


class LabelShare(BaseModel):
    count: int
    percent: float


class SentimentDistribution(BaseModel):
    positive: LabelShare
    neutral: LabelShare
    negative: LabelShare


class SourceSummary(BaseModel):
    source: str
    source_type: SourceType
    weight: float
    is_active: bool
    review_count: int
    positive: int
    neutral: int
    negative: int
    average_compound: Optional[float]


class RatingStats(BaseModel):
    count: int
    average: Optional[float]
    distribution: Dict[str, int]


class TopicSummaryOut(BaseModel):
    topic_slug: str
    topic_name: str
    score: Optional[float]
    verdict: str
    reliability: float
    headline: str
    sentiment: SentimentDistribution
    by_source: List[SourceSummary]
    ratings: RatingStats
    top_positive: List[ReviewOut]
    top_negative: List[ReviewOut]

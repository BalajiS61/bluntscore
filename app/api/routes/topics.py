"""Topic endpoints: search, details, scores, summaries and reviews."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import topic_from_path
from app.core.errors import BadRequestError
from app.db.database import get_db
from app.models import SentimentLabel, Topic
from app.schemas.common import Page, error_responses
from app.schemas.topics import (
    LabelShare,
    ReviewOut,
    ScoreOut,
    SentimentDistribution,
    SourceSummary,
    TopicCreate,
    TopicDetailOut,
    TopicOut,
    TopicSummaryOut,
    RatingStats,
)
from app.services import topic_service
from app.services.scoring_service import compute_topic_breakdown, recompute_topic_score

router = APIRouter(prefix="/topics", tags=["Topics"])
NOT_FOUND = error_responses(404)

TopicSort = Literal["-score", "score", "name", "-name", "-reviews", "reviews", "recent"]
ReviewSort = Literal["recent", "oldest", "-compound", "compound"]


@router.get("", response_model=Page[TopicOut], summary="Search and list topics",
            responses=error_responses(400))
def list_topics(
    q: Optional[str] = Query(None, max_length=100, description="Search name, category or description"),
    category: Optional[str] = Query(None, max_length=60),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    max_score: Optional[float] = Query(None, ge=0, le=100),
    sort: TopicSort = Query("-score", description="'-' means descending"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[TopicOut]:
    if min_score is not None and max_score is not None and min_score > max_score:
        raise BadRequestError("min_score cannot be greater than max_score")
    items, total = topic_service.search_topics(db, q, category, min_score, max_score, sort, limit, offset)
    return Page[TopicOut](items=[TopicOut.from_topic(t) for t in items], total=total, limit=limit, offset=offset)


@router.post("", response_model=TopicOut, status_code=status.HTTP_201_CREATED, summary="Create a topic",
             responses=error_responses(409))
def create_topic(payload: TopicCreate, db: Session = Depends(get_db)) -> TopicOut:
    topic = topic_service.create_topic(db, payload.name, payload.category, payload.description)
    return TopicOut.from_topic(topic)


@router.get("/{slug}", response_model=TopicDetailOut, summary="Get one topic", responses=NOT_FOUND)
def get_topic(topic: Topic = Depends(topic_from_path), db: Session = Depends(get_db)) -> TopicDetailOut:
    count, average, _ = topic_service.rating_stats(db, topic.id)
    return TopicDetailOut(
        **TopicOut.from_topic(topic).model_dump(),
        rating_count=count,
        average_rating=average,
        source_count=topic_service.source_count(db, topic.id),
    )


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a topic and its data", responses=NOT_FOUND)
def delete_topic(topic: Topic = Depends(topic_from_path), db: Session = Depends(get_db)) -> Response:
    topic_service.delete_topic(db, topic)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{slug}/score", response_model=ScoreOut, summary="Full score breakdown", responses=NOT_FOUND)
def get_score(topic: Topic = Depends(topic_from_path), db: Session = Depends(get_db)) -> ScoreOut:
    return ScoreOut.build(topic, compute_topic_breakdown(db, topic))


@router.post("/{slug}/score/refresh", response_model=ScoreOut, summary="Re-analyze and rescore a topic", responses=NOT_FOUND)
def refresh_score(topic: Topic = Depends(topic_from_path), db: Session = Depends(get_db)) -> ScoreOut:
    return ScoreOut.build(topic, recompute_topic_score(db, topic))


@router.get("/{slug}/summary", response_model=TopicSummaryOut, summary="Sentiment summary", responses=NOT_FOUND)
def get_summary(topic: Topic = Depends(topic_from_path), db: Session = Depends(get_db)) -> TopicSummaryOut:
    breakdown = compute_topic_breakdown(db, topic)
    counts = {
        "positive": breakdown.positive_count,
        "neutral": breakdown.neutral_count,
        "negative": breakdown.negative_count,
    }
    labelled = sum(counts.values())

    def share(label: str) -> LabelShare:
        n = counts[label]
        return LabelShare(count=n, percent=round(n / labelled * 100, 1) if labelled else 0.0)

    by_source = [SourceSummary(**s) for s in topic_service.source_breakdown(db, topic)]
    active_sources = sum(1 for s in by_source if s.is_active)
    rating_count, rating_avg, distribution = topic_service.rating_stats(db, topic.id)

    return TopicSummaryOut(
        topic_slug=topic.slug,
        topic_name=topic.name,
        score=breakdown.score,
        verdict=breakdown.verdict,
        reliability=breakdown.reliability,
        headline=topic_service.build_headline(
            breakdown.verdict, breakdown.score, counts, labelled, active_sources
        ),
        sentiment=SentimentDistribution(
            positive=share("positive"), neutral=share("neutral"), negative=share("negative")
        ),
        by_source=by_source,
        ratings=RatingStats(count=rating_count, average=rating_avg, distribution=distribution),
        top_positive=[ReviewOut.from_review(r) for r in topic_service.top_reviews(db, topic, SentimentLabel.POSITIVE)],
        top_negative=[ReviewOut.from_review(r) for r in topic_service.top_reviews(db, topic, SentimentLabel.NEGATIVE)],
    )


@router.get("/{slug}/reviews", response_model=Page[ReviewOut], summary="List a topic's reviews", responses=NOT_FOUND)
def list_reviews(
    label: Optional[SentimentLabel] = Query(None),
    source: Optional[str] = Query(None, max_length=80),
    sort: ReviewSort = Query("recent"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    topic: Topic = Depends(topic_from_path),
    db: Session = Depends(get_db),
) -> Page[ReviewOut]:
    items, total = topic_service.list_reviews(db, topic, label, source, sort, limit, offset)
    return Page[ReviewOut](items=[ReviewOut.from_review(r) for r in items], total=total, limit=limit, offset=offset)

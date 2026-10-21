"""Recomputes a topic's BluntScore from its stored reviews and ratings."""
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Review, Source, Topic, UserRating
from app.models.mixins import utcnow
from app.scoring.engine import ReviewSignal, ScoreBreakdown, ScoringConfig, compute_score
from app.services.sentiment_service import analyze_reviews


def get_scoring_config() -> ScoringConfig:
    settings = get_settings()
    return ScoringConfig(
        half_life_days=settings.scoring_half_life_days,
        prior_strength=settings.scoring_prior_strength,
        rating_weight=settings.scoring_rating_weight,
    )


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite returns naive datetimes; we always store UTC, so attach it back."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def build_review_signals(db: Session, topic_id: int) -> list[ReviewSignal]:
    """Reviews from active sources only, converted into scoring-engine inputs."""
    rows = db.execute(
        select(Review, Source.weight)
        .join(Source, Review.source_id == Source.id)
        .where(Review.topic_id == topic_id, Source.is_active == True)  # noqa: E712
    ).all()
    return [
        ReviewSignal(
            compound=review.sentiment_compound or 0.0,
            confidence=review.sentiment_confidence or 0.0,
            source_weight=weight,
            timestamp=_as_utc(review.published_at or review.created_at),
            label=review.sentiment_label.value if review.sentiment_label else None,
        )
        for review, weight in rows
    ]


def recompute_topic_score(
    db: Session,
    topic: Topic,
    config: Optional[ScoringConfig] = None,
    now: Optional[datetime] = None,
) -> ScoreBreakdown:
    """Analyze any new reviews, recompute the score and cache it on the topic."""
    analyze_reviews(db, topic_id=topic.id)

    signals = build_review_signals(db, topic.id)
    ratings = db.scalars(select(UserRating.rating).where(UserRating.topic_id == topic.id)).all()
    breakdown = compute_score(signals, ratings, config or get_scoring_config(), now)

    topic.sentiment_score = breakdown.score
    topic.review_count = breakdown.review_count
    topic.positive_count = breakdown.positive_count
    topic.neutral_count = breakdown.neutral_count
    topic.negative_count = breakdown.negative_count
    topic.last_scored_at = utcnow()
    db.commit()
    return breakdown


def recompute_all_topics(db: Session, config: Optional[ScoringConfig] = None) -> Dict[int, ScoreBreakdown]:
    return {topic.id: recompute_topic_score(db, topic, config) for topic in db.scalars(select(Topic)).all()}

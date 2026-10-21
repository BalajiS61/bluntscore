"""Runs the NLP analyzer over reviews stored in the database."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Review
from app.models.mixins import utcnow
from app.nlp.analyzer import SentimentAnalyzer, SentimentResult, get_analyzer


def apply_result(review: Review, result: SentimentResult) -> None:
    review.sentiment_label = result.label
    review.sentiment_compound = result.compound
    review.sentiment_confidence = result.confidence
    review.analyzed_at = utcnow()


def analyze_reviews(
    db: Session,
    topic_id: Optional[int] = None,
    reanalyze: bool = False,
    analyzer: Optional[SentimentAnalyzer] = None,
) -> int:
    """Analyze reviews and save the results. Returns how many were analyzed.

    By default only reviews never analyzed before are processed;
    reanalyze=True re-runs all of them (e.g. after changing thresholds).
    """
    analyzer = analyzer or get_analyzer()
    stmt = select(Review)
    if topic_id is not None:
        stmt = stmt.where(Review.topic_id == topic_id)
    if not reanalyze:
        stmt = stmt.where(Review.analyzed_at.is_(None))

    reviews = db.scalars(stmt).all()
    for review in reviews:
        apply_result(review, analyzer.analyze(review.text))
    db.commit()
    return len(reviews)

"""BluntScore algorithm: turns many review signals + user ratings into one 0-100 score.

Pure functions only (no database, no web framework) so the maths is easy to test.

How the score is built
----------------------
1. Each review's VADER compound (-1..+1) is mapped to 0..100:   s = (compound + 1) * 50
2. Each review gets a weight:
       w = source_weight * confidence * recency
   - source_weight : trusted sources count more (Source.weight, default 1.0)
   - confidence    : borderline NLP calls count less (0.5..1.0, 0 for empty text)
   - recency       : 0.5 ** (age_days / half_life_days), so a review loses half
                     its influence every half_life_days (default 180)
3. Bayesian smoothing toward a neutral prior (50) with strength k "virtual reviews":
       review_score = (sum(w * s) + k * 50) / (sum(w) + k)
   One glowing review can't produce 100; the score only moves far from 50
   when there is enough evidence.
4. User star ratings (1..5) map to 0..100 as (stars - 1) * 25 and are smoothed
   the same way.
5. Final score = (1 - rating_weight) * review_score + rating_weight * rating_score
   (if only one of the two exists, that one is used alone; if neither, no score).
6. reliability = evidence / (evidence + k), 0..1: how much of the score comes from
   real data rather than the neutral prior.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence


@dataclass(frozen=True)
class ScoringConfig:
    half_life_days: float = 180.0
    prior_strength: float = 5.0
    prior_score: float = 50.0
    rating_weight: float = 0.3

    def __post_init__(self) -> None:
        if self.half_life_days <= 0:
            raise ValueError("half_life_days must be > 0")
        if self.prior_strength < 0:
            raise ValueError("prior_strength must be >= 0")
        if not 0 <= self.prior_score <= 100:
            raise ValueError("prior_score must be within 0..100")
        if not 0 <= self.rating_weight <= 1:
            raise ValueError("rating_weight must be within 0..1")


@dataclass(frozen=True)
class ReviewSignal:
    compound: float
    confidence: float
    source_weight: float = 1.0
    timestamp: Optional[datetime] = None
    label: Optional[str] = None  # "positive" / "neutral" / "negative"


@dataclass(frozen=True)
class ScoreBreakdown:
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


# ---------- building blocks ----------

def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def compound_to_score(compound: float) -> float:
    return (_clamp(compound, -1.0, 1.0) + 1.0) * 50.0


def rating_to_score(stars: int) -> float:
    if not 1 <= stars <= 5:
        raise ValueError(f"Rating must be 1..5, got {stars}")
    return (stars - 1) * 25.0


def recency_weight(timestamp: Optional[datetime], now: datetime, half_life_days: float) -> float:
    if timestamp is None:
        return 1.0
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - timestamp).total_seconds() / 86400.0)
    return 0.5 ** (age_days / half_life_days)


def review_weight(signal: ReviewSignal, now: datetime, config: ScoringConfig) -> float:
    return (
        max(0.0, signal.source_weight)
        * _clamp(signal.confidence, 0.0, 1.0)
        * recency_weight(signal.timestamp, now, config.half_life_days)
    )


def smoothed_mean(weighted_sum: float, total_weight: float, config: ScoringConfig) -> float:
    k = config.prior_strength
    return (weighted_sum + k * config.prior_score) / (total_weight + k)


def verdict_for(score: Optional[float]) -> str:
    if score is None:
        return "Not enough data"
    if score < 20:
        return "Very negative"
    if score < 40:
        return "Negative"
    if score < 60:
        return "Mixed"
    if score < 80:
        return "Positive"
    return "Very positive"


# ---------- main entry point ----------

def compute_score(
    reviews: Sequence[ReviewSignal],
    ratings: Iterable[int] = (),
    config: Optional[ScoringConfig] = None,
    now: Optional[datetime] = None,
) -> ScoreBreakdown:
    config = config or ScoringConfig()
    now = now or datetime.now(timezone.utc)
    ratings = list(ratings)

    # Reviews
    weighted_sum = total_weight = 0.0
    for signal in reviews:
        w = review_weight(signal, now, config)
        weighted_sum += w * compound_to_score(signal.compound)
        total_weight += w
    review_score = smoothed_mean(weighted_sum, total_weight, config) if total_weight > 0 else None

    # User ratings
    rating_scores = [rating_to_score(r) for r in ratings]
    rating_score = (
        smoothed_mean(sum(rating_scores), len(rating_scores), config) if rating_scores else None
    )
    average_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

    # Combine
    if review_score is not None and rating_score is not None:
        score = (1 - config.rating_weight) * review_score + config.rating_weight * rating_score
    elif review_score is not None:
        score = review_score
    elif rating_score is not None:
        score = rating_score
    else:
        score = None

    evidence = total_weight + len(rating_scores)
    k = config.prior_strength
    reliability = evidence / (evidence + k) if evidence > 0 else 0.0

    labels = [s.label for s in reviews]
    final = round(_clamp(score, 0.0, 100.0), 1) if score is not None else None
    return ScoreBreakdown(
        score=final,
        verdict=verdict_for(final),
        review_score=round(review_score, 1) if review_score is not None else None,
        rating_score=round(rating_score, 1) if rating_score is not None else None,
        average_rating=average_rating,
        review_count=len(reviews),
        rating_count=len(ratings),
        positive_count=labels.count("positive"),
        neutral_count=labels.count("neutral"),
        negative_count=labels.count("negative"),
        reliability=round(reliability, 3),
    )

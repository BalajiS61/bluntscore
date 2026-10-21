"""Pure scoring-maths tests (no database)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.scoring.engine import (
    ReviewSignal,
    ScoringConfig,
    compound_to_score,
    compute_score,
    rating_to_score,
    recency_weight,
    verdict_for,
)

NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)
POS = ReviewSignal(compound=0.9, confidence=0.97, label="positive")
NEG = ReviewSignal(compound=-0.9, confidence=0.97, label="negative")


# ---------- building blocks ----------

def test_compound_and_rating_mapping():
    assert compound_to_score(-1) == 0
    assert compound_to_score(0) == 50
    assert compound_to_score(1) == 100
    assert rating_to_score(1) == 0
    assert rating_to_score(3) == 50
    assert rating_to_score(5) == 100


def test_rating_out_of_range_rejected():
    with pytest.raises(ValueError):
        rating_to_score(6)


def test_recency_halves_every_half_life():
    assert recency_weight(NOW, NOW, 180) == 1.0
    assert recency_weight(NOW - timedelta(days=180), NOW, 180) == pytest.approx(0.5)
    assert recency_weight(NOW - timedelta(days=360), NOW, 180) == pytest.approx(0.25)
    assert recency_weight(None, NOW, 180) == 1.0


def test_verdicts():
    assert verdict_for(None) == "Not enough data"
    assert verdict_for(10) == "Very negative"
    assert verdict_for(30) == "Negative"
    assert verdict_for(50) == "Mixed"
    assert verdict_for(70) == "Positive"
    assert verdict_for(90) == "Very positive"


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        ScoringConfig(rating_weight=1.5)
    with pytest.raises(ValueError):
        ScoringConfig(half_life_days=0)


# ---------- full score ----------

def test_no_data_gives_no_score():
    result = compute_score([], [], now=NOW)
    assert result.score is None
    assert result.verdict == "Not enough data"
    assert result.reliability == 0.0


def test_single_review_is_smoothed_toward_neutral():
    assert compute_score([POS], now=NOW).score == 57.3


def test_many_positive_reviews_score_high():
    result = compute_score([POS] * 20, now=NOW)
    assert result.score == 85.8
    assert result.verdict == "Very positive"
    assert result.positive_count == 20


def test_many_negative_reviews_score_low():
    result = compute_score([NEG] * 20, now=NOW)
    assert result.score == 14.2
    assert result.verdict == "Very negative"


def test_balanced_reviews_score_50():
    assert compute_score([POS] * 10 + [NEG] * 10, now=NOW).score == 50.0


def test_trusted_source_outweighs_noisy_source():
    trusted_negative = ReviewSignal(-0.9, 0.97, source_weight=3.0)
    noisy_positive = ReviewSignal(0.9, 0.97, source_weight=0.5)
    assert compute_score([trusted_negative] * 5 + [noisy_positive] * 5, now=NOW).score == 25.2


def test_recent_reviews_outweigh_old_ones():
    old_positive = ReviewSignal(0.9, 0.97, timestamp=NOW - timedelta(days=730))
    new_negative = ReviewSignal(-0.9, 0.97, timestamp=NOW - timedelta(days=1))
    assert compute_score([old_positive] * 5 + [new_negative] * 5, now=NOW).score == 29.8


def test_zero_confidence_reviews_are_ignored():
    result = compute_score([ReviewSignal(0.9, 0.0)] * 5, now=NOW)
    assert result.score is None
    assert result.review_count == 5


def test_ratings_only():
    assert compute_score([], [5] * 20, now=NOW).score == 90.0
    assert compute_score([], [1] * 20, now=NOW).score == 10.0


def test_reviews_and_ratings_are_blended_70_30():
    result = compute_score([POS] * 20, [1] * 20, now=NOW)
    assert result.review_score == 85.8
    assert result.rating_score == 10.0
    assert result.score == 63.0
    assert result.average_rating == 1.0


def test_more_evidence_means_more_reliability():
    assert compute_score([POS] * 2, now=NOW).reliability == 0.28
    assert compute_score([POS] * 50, now=NOW).reliability == 0.907


def test_naive_timestamps_are_treated_as_utc():
    naive = ReviewSignal(0.9, 0.97, timestamp=datetime(2026, 10, 21))
    assert compute_score([naive], now=NOW).score == 57.3


@pytest.mark.parametrize("compound", [-5, -1, -0.3, 0, 0.3, 1, 5])
def test_score_always_within_0_and_100(compound):
    result = compute_score([ReviewSignal(compound, 1.0)] * 100, [1, 5] * 10, now=NOW)
    assert 0 <= result.score <= 100

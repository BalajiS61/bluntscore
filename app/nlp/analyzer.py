"""Sentiment classifier built on VADER with a review-specific lexicon.

Output for each text:
  label       positive / neutral / negative
  compound    VADER compound score, -1 (most negative) .. +1 (most positive)
  confidence  0..1, how far the compound sits inside its label's band
  positive/neutral/negative   VADER's proportion of each sentiment in the text
"""
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, List

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.core.config import get_settings
from app.models.enums import SentimentLabel
from app.nlp.lexicon import REVIEW_LEXICON
from app.nlp.preprocess import clean_text


@dataclass(frozen=True)
class SentimentResult:
    label: SentimentLabel
    compound: float
    confidence: float
    positive: float
    neutral: float
    negative: float
    cleaned_text: str


class SentimentAnalyzer:
    def __init__(self, positive_threshold: float = 0.05, negative_threshold: float = -0.05):
        if not (-1 < negative_threshold < positive_threshold < 1):
            raise ValueError("Require -1 < negative_threshold < positive_threshold < 1")
        self.positive_threshold = positive_threshold
        self.negative_threshold = negative_threshold
        self._vader = SentimentIntensityAnalyzer()
        self._vader.lexicon.update(REVIEW_LEXICON)

    def classify(self, compound: float) -> SentimentLabel:
        if compound >= self.positive_threshold:
            return SentimentLabel.POSITIVE
        if compound <= self.negative_threshold:
            return SentimentLabel.NEGATIVE
        return SentimentLabel.NEUTRAL

    def confidence(self, compound: float, label: SentimentLabel) -> float:
        """0.5 right at a label boundary, rising to 1.0 at the far end of the band."""
        pos_t, neg_t = self.positive_threshold, self.negative_threshold
        if label is SentimentLabel.POSITIVE:
            distance, span = compound - pos_t, 1 - pos_t
        elif label is SentimentLabel.NEGATIVE:
            distance, span = neg_t - compound, neg_t + 1
        else:
            half_width = (pos_t - neg_t) / 2
            center = (pos_t + neg_t) / 2
            distance, span = half_width - abs(compound - center), half_width
        ratio = min(1.0, max(0.0, distance / span))
        return round(0.5 + 0.5 * ratio, 4)

    def analyze(self, text: str) -> SentimentResult:
        cleaned = clean_text(text)
        if not cleaned:
            # Nothing left to judge (e.g. the text was only a URL): neutral, no confidence
            return SentimentResult(SentimentLabel.NEUTRAL, 0.0, 0.0, 0.0, 1.0, 0.0, cleaned)

        scores = self._vader.polarity_scores(cleaned)
        compound = round(scores["compound"], 4)
        label = self.classify(compound)
        return SentimentResult(
            label=label,
            compound=compound,
            confidence=self.confidence(compound, label),
            positive=round(scores["pos"], 4),
            neutral=round(scores["neu"], 4),
            negative=round(scores["neg"], 4),
            cleaned_text=cleaned,
        )

    def analyze_batch(self, texts: Iterable[str]) -> List[SentimentResult]:
        return [self.analyze(t) for t in texts]


@lru_cache
def get_analyzer() -> SentimentAnalyzer:
    """One shared analyzer per process (loading the VADER lexicon is the slow part)."""
    settings = get_settings()
    return SentimentAnalyzer(
        positive_threshold=settings.sentiment_positive_threshold,
        negative_threshold=settings.sentiment_negative_threshold,
    )

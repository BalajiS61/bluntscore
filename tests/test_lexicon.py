"""Regression tests for words added to the custom review lexicon."""
import pytest

from app.models.enums import SentimentLabel
from app.nlp.analyzer import SentimentAnalyzer


@pytest.fixture(scope="module")
def analyzer():
    return SentimentAnalyzer()


@pytest.mark.parametrize(
    "text",
    ["The battery is mediocre", "The sequel was underwhelming", "Subpar build quality"],
)
def test_mild_complaint_words_are_negative(analyzer, text):
    assert analyzer.analyze(text).label is SentimentLabel.NEGATIVE

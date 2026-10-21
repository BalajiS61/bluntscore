"""NLP engine tests: cleaning, classification, confidence, edge cases."""
import pytest

from app.models.enums import SentimentLabel
from app.nlp.analyzer import SentimentAnalyzer
from app.nlp.preprocess import clean_text


@pytest.fixture(scope="module")
def analyzer():
    return SentimentAnalyzer()


# ---------- preprocessing ----------

def test_clean_text_removes_noise_but_keeps_signals():
    raw = "Check https://x.com/abc &amp; <b>WOW</b> @john #awesome!!!"
    assert clean_text(raw) == "Check & WOW awesome!!!"


def test_clean_text_shortens_elongated_words():
    assert clean_text("This is gooooood") == "This is good"


def test_clean_text_handles_empty():
    assert clean_text("") == ""
    assert clean_text("   ") == ""


# ---------- classification ----------

def test_clear_positive(analyzer):
    result = analyzer.analyze("I absolutely love this phone, the camera is amazing!")
    assert result.label is SentimentLabel.POSITIVE
    assert result.compound > 0.5


def test_clear_negative(analyzer):
    result = analyzer.analyze("Terrible battery, it died after two hours. Total waste of money.")
    assert result.label is SentimentLabel.NEGATIVE
    assert result.compound < -0.5


def test_neutral_fact(analyzer):
    result = analyzer.analyze("The phone comes in black and white.")
    assert result.label is SentimentLabel.NEUTRAL


def test_negation_flips_sentiment(analyzer):
    assert analyzer.analyze("This is good").label is SentimentLabel.POSITIVE
    assert analyzer.analyze("This is not good").label is SentimentLabel.NEGATIVE


def test_custom_review_lexicon(analyzer):
    result = analyzer.analyze("Overpriced and laggy")
    assert result.label is SentimentLabel.NEGATIVE


def test_text_with_only_noise_is_neutral_with_zero_confidence(analyzer):
    result = analyzer.analyze("https://example.com @someone")
    assert result.label is SentimentLabel.NEUTRAL
    assert result.compound == 0.0
    assert result.confidence == 0.0


# ---------- confidence & ranges ----------

@pytest.mark.parametrize(
    "text",
    ["Best purchase ever!!!", "meh", "Awful. Just awful.", "It works.", "not bad at all"],
)
def test_scores_stay_in_range(analyzer, text):
    r = analyzer.analyze(text)
    assert -1 <= r.compound <= 1
    assert 0 <= r.confidence <= 1
    assert abs(r.positive + r.neutral + r.negative - 1) < 0.01


def test_confidence_rules(analyzer):
    assert analyzer.confidence(0.05, SentimentLabel.POSITIVE) == 0.5   # right at the boundary
    assert analyzer.confidence(1.0, SentimentLabel.POSITIVE) == 1.0    # strongest possible
    assert analyzer.confidence(-1.0, SentimentLabel.NEGATIVE) == 1.0
    assert analyzer.confidence(0.0, SentimentLabel.NEUTRAL) == 1.0     # dead-centre neutral


def test_invalid_thresholds_rejected():
    with pytest.raises(ValueError):
        SentimentAnalyzer(positive_threshold=-0.1, negative_threshold=0.1)


def test_batch_keeps_order(analyzer):
    results = analyzer.analyze_batch(["I love it", "I hate it", "It is a phone"])
    assert [r.label for r in results] == [
        SentimentLabel.POSITIVE,
        SentimentLabel.NEGATIVE,
        SentimentLabel.NEUTRAL,
    ]

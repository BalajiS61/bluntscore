"""Analyzing reviews stored in the database."""
from app.models import Review, SentimentLabel, Source, SourceType, Topic
from app.services.sentiment_service import analyze_reviews


def _seed(db_session):
    topic = Topic(name="Pixel 9")
    source = Source(name="amazon", source_type=SourceType.ECOMMERCE)
    db_session.add_all([topic, source])
    db_session.commit()
    db_session.add_all(
        [
            Review(topic=topic, source=source, text="Amazing camera"),
            Review(topic=topic, source=source, text="Awful battery life"),
            Review(topic=topic, source=source, text="It arrived on Tuesday"),
        ]
    )
    db_session.commit()
    return topic


def test_analyze_pending_reviews(db_session):
    topic = _seed(db_session)
    assert analyze_reviews(db_session) == 3

    labels = {r.text: r.sentiment_label for r in db_session.query(Review).all()}
    assert labels["Amazing camera"] is SentimentLabel.POSITIVE
    assert labels["Awful battery life"] is SentimentLabel.NEGATIVE
    assert labels["It arrived on Tuesday"] is SentimentLabel.NEUTRAL

    for review in topic.reviews:
        assert review.analyzed_at is not None
        assert -1 <= review.sentiment_compound <= 1
        assert 0 <= review.sentiment_confidence <= 1


def test_already_analyzed_reviews_are_skipped(db_session):
    _seed(db_session)
    assert analyze_reviews(db_session) == 3
    assert analyze_reviews(db_session) == 0
    assert analyze_reviews(db_session, reanalyze=True) == 3


def test_analyze_only_one_topic(db_session):
    topic = _seed(db_session)
    other = Topic(name="Galaxy S25")
    db_session.add(other)
    db_session.commit()
    db_session.add(Review(topic=other, source=topic.reviews[0].source, text="Pretty good"))
    db_session.commit()

    assert analyze_reviews(db_session, topic_id=other.id) == 1
    assert analyze_reviews(db_session) == 3

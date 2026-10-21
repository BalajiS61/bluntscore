"""Scoring against the database: analysis, filtering, caching on the topic."""
from app.models import Review, Source, SourceType, Topic, UserRating
from app.services.scoring_service import recompute_all_topics, recompute_topic_score


def _seed(db_session):
    topic = Topic(name="Pixel 9")
    amazon = Source(name="amazon", source_type=SourceType.ECOMMERCE, weight=1.0)
    spam = Source(name="spam-site", source_type=SourceType.OTHER, weight=1.0, is_active=False)
    db_session.add_all([topic, amazon, spam])
    db_session.commit()
    db_session.add_all(
        [
            Review(topic=topic, source=amazon, text="I absolutely love this phone, amazing camera!"),
            Review(topic=topic, source=amazon, text="Great battery life and a gorgeous screen"),
            Review(topic=topic, source=amazon, text="It arrived on Tuesday"),
            Review(topic=topic, source=spam, text="Worst garbage ever, total scam, horrible"),
            UserRating(topic=topic, user_id="u1", rating=5),
            UserRating(topic=topic, user_id="u2", rating=4),
        ]
    )
    db_session.commit()
    return topic


def test_recompute_scores_and_caches_on_topic(db_session):
    topic = _seed(db_session)
    breakdown = recompute_topic_score(db_session, topic)

    assert breakdown.score is not None and breakdown.score > 50
    assert breakdown.review_count == 3          # inactive source excluded
    assert breakdown.positive_count == 2
    assert breakdown.neutral_count == 1
    assert breakdown.negative_count == 0
    assert breakdown.rating_count == 2
    assert breakdown.average_rating == 4.5

    db_session.refresh(topic)
    assert topic.sentiment_score == breakdown.score
    assert topic.review_count == 3
    assert topic.positive_count == 2
    assert topic.last_scored_at is not None


def test_recompute_analyzes_new_reviews_automatically(db_session):
    topic = _seed(db_session)
    recompute_topic_score(db_session, topic)
    for review in topic.reviews:
        assert review.analyzed_at is not None


def test_new_negative_reviews_lower_the_score(db_session):
    topic = _seed(db_session)
    before = recompute_topic_score(db_session, topic).score

    amazon = db_session.query(Source).filter_by(name="amazon").one()
    for i in range(5):
        db_session.add(Review(topic=topic, source=amazon, text=f"Terrible, it broke after {i + 1} days"))
    db_session.commit()

    after = recompute_topic_score(db_session, topic).score
    assert after < before


def test_topic_without_data_has_no_score(db_session):
    topic = Topic(name="Brand new gadget")
    db_session.add(topic)
    db_session.commit()

    breakdown = recompute_topic_score(db_session, topic)
    assert breakdown.score is None
    assert breakdown.verdict == "Not enough data"
    assert topic.sentiment_score is None
    assert topic.review_count == 0


def test_recompute_all_topics(db_session):
    _seed(db_session)
    db_session.add(Topic(name="Empty topic"))
    db_session.commit()

    results = recompute_all_topics(db_session)
    assert len(results) == 2
    assert sum(1 for b in results.values() if b.score is not None) == 1

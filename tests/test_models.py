"""Database-layer tests: relationships, constraints and cascades."""
import pytest
from sqlalchemy.exc import IntegrityError, StatementError

from app.models import Review, SentimentLabel, Source, SourceType, Topic, UserRating


def make_topic(session, name="Apple iPhone 16"):
    topic = Topic(name=name, category="smartphones")
    session.add(topic)
    session.commit()
    return topic


def make_source(session, name="amazon", source_type=SourceType.ECOMMERCE, weight=1.2):
    source = Source(name=name, source_type=source_type, weight=weight)
    session.add(source)
    session.commit()
    return source


def test_topic_slug_is_generated(db_session):
    topic = make_topic(db_session, name="  Apple iPhone 16 Pro! ")
    assert topic.name == "Apple iPhone 16 Pro!"
    assert topic.slug == "apple-iphone-16-pro"
    assert topic.review_count == 0
    assert topic.sentiment_score is None
    assert topic.created_at is not None


def test_empty_topic_name_rejected(db_session):
    with pytest.raises(ValueError):
        Topic(name="   ")


def test_full_object_graph(db_session):
    topic = make_topic(db_session)
    source = make_source(db_session)

    review = Review(
        topic=topic,
        source=source,
        text="Battery life is amazing",
        sentiment_label=SentimentLabel.POSITIVE,
        sentiment_compound=0.82,
        sentiment_confidence=0.9,
    )
    rating = UserRating(topic=topic, user_id="user_1", rating=5, comment="Love it")
    db_session.add_all([review, rating])
    db_session.commit()

    db_session.refresh(topic)
    assert len(topic.reviews) == 1
    assert len(topic.ratings) == 1
    assert topic.reviews[0].source.name == "amazon"
    assert topic.reviews[0].sentiment_label is SentimentLabel.POSITIVE
    assert len(review.content_hash) == 64


def test_duplicate_review_same_topic_rejected(db_session):
    topic = make_topic(db_session)
    source = make_source(db_session)
    db_session.add(Review(topic=topic, source=source, text="Great camera"))
    db_session.commit()

    # Same text with different case/spacing counts as a duplicate
    db_session.add(Review(topic=topic, source=source, text="  great   CAMERA "))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_same_review_text_allowed_on_different_topics(db_session):
    topic_a = make_topic(db_session, name="Topic A")
    topic_b = make_topic(db_session, name="Topic B")
    source = make_source(db_session)
    db_session.add_all(
        [
            Review(topic=topic_a, source=source, text="Totally worth it"),
            Review(topic=topic_b, source=source, text="Totally worth it"),
        ]
    )
    db_session.commit()
    assert db_session.query(Review).count() == 2


def test_empty_review_text_rejected(db_session):
    with pytest.raises(ValueError):
        Review(text="   ")


def test_one_rating_per_user_per_topic(db_session):
    topic = make_topic(db_session)
    db_session.add(UserRating(topic=topic, user_id="user_1", rating=4))
    db_session.commit()

    db_session.add(UserRating(topic=topic, user_id="user_1", rating=2))
    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize("bad_rating", [0, 6])
def test_rating_out_of_range_rejected(db_session, bad_rating):
    topic = make_topic(db_session)
    db_session.add(UserRating(topic=topic, user_id="user_1", rating=bad_rating))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_topic_score_must_be_0_to_100(db_session):
    topic = make_topic(db_session)
    topic.sentiment_score = 150
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_source_weight_must_be_positive(db_session):
    db_session.add(Source(name="bad", weight=0))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_invalid_sentiment_label_rejected(db_session):
    topic = make_topic(db_session)
    source = make_source(db_session)
    db_session.add(Review(topic=topic, source=source, text="hmm", sentiment_label="great"))
    with pytest.raises((StatementError, LookupError)):
        db_session.commit()


def test_deleting_topic_removes_its_reviews_and_ratings(db_session):
    topic = make_topic(db_session)
    source = make_source(db_session)
    db_session.add_all(
        [
            Review(topic=topic, source=source, text="Good"),
            Review(topic=topic, source=source, text="Bad"),
            UserRating(topic=topic, user_id="user_1", rating=3),
        ]
    )
    db_session.commit()

    db_session.delete(topic)
    db_session.commit()

    assert db_session.query(Review).count() == 0
    assert db_session.query(UserRating).count() == 0
    assert db_session.query(Source).count() == 1  # sources are independent of topics

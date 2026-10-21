"""Demo: seed three topics in a throwaway in-memory database and print their BluntScores.

Run from the project folder:   python -m scripts.demo_scoring
Your real bluntscore.db is not touched.
"""
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.database import Base, enable_sqlite_foreign_keys
from app.models import Review, Source, SourceType, Topic, UserRating
from app.models.mixins import utcnow
from app.services.scoring_service import recompute_topic_score

DATA = {
    "Pixel 9": {
        "reviews": [
            ("amazon", "Absolutely love it, the camera is stunning!", 2),
            ("amazon", "Battery easily lasts two days, fantastic", 10),
            ("reddit", "Smooth, snappy and reliable. Best phone I've owned", 5),
            ("reddit", "A bit pricey but worth it", 30),
            ("news", "The display is bright and the build feels durable", 20),
        ],
        "ratings": [5, 5, 4, 4, 5],
    },
    "Budget Earbuds X": {
        "reviews": [
            ("amazon", "Sound is okay for the price", 3),
            ("amazon", "Right earbud died after a week, defective", 4),
            ("reddit", "Laggy bluetooth and flimsy case", 8),
            ("reddit", "Decent bass, average everything else", 15),
            ("news", "Comfortable fit, mediocre battery", 40),
        ],
        "ratings": [3, 2, 3, 2],
    },
    "CrashyApp 2.0": {
        "reviews": [
            ("reddit", "Crashes every time I open it. Total garbage", 1),
            ("reddit", "Buggy mess, I want a refund", 2),
            ("amazon", "Terrible update, everything is slower", 3),
            ("news", "Version 1 was great, but 2.0 is a disappointment", 6),
            ("amazon", "Loved it two years ago", 730),
        ],
        "ratings": [1, 1, 2],
    },
}

SOURCES = [
    ("amazon", SourceType.ECOMMERCE, 1.0),
    ("reddit", SourceType.FORUM, 0.8),
    ("news", SourceType.NEWS, 1.5),
]


def main() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()

    sources = {name: Source(name=name, source_type=kind, weight=w) for name, kind, w in SOURCES}
    db.add_all(sources.values())
    db.commit()

    now = utcnow()
    for topic_name, data in DATA.items():
        topic = Topic(name=topic_name)
        db.add(topic)
        db.commit()
        for source_name, text, days_ago in data["reviews"]:
            db.add(Review(topic=topic, source=sources[source_name], text=text,
                          published_at=now - timedelta(days=days_ago)))
        for i, stars in enumerate(data["ratings"]):
            db.add(UserRating(topic=topic, user_id=f"user_{i}", rating=stars))
        db.commit()

        b = recompute_topic_score(db, topic)
        print(f"\n=== {topic_name} ===")
        print(f"  BluntScore    : {b.score}  ({b.verdict})")
        print(f"  Review score  : {b.review_score}   from {b.review_count} reviews "
              f"(+{b.positive_count} / ={b.neutral_count} / -{b.negative_count})")
        print(f"  Rating score  : {b.rating_score}   avg {b.average_rating} stars from {b.rating_count} ratings")
        print(f"  Reliability   : {b.reliability}")
        for review in topic.reviews:
            print(f"    [{review.sentiment_label.value:>8} {review.sentiment_compound:+.3f}] {review.text}")

    db.close()


if __name__ == "__main__":
    main()

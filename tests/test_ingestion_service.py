"""Ingestion pipeline: storage, de-duplication, rescoring, sample dataset."""
from app.ingestion.adapters import ParsedBatch, RawReview, RowError
from app.models import Review, Source, SourceType, Topic, UserRating
from app.services.ingestion_service import (
    get_or_create_source,
    get_or_create_topic,
    ingest_batch,
    load_sample_dataset,
)


def _batch(*texts, ids=None):
    ids = ids or [None] * len(texts)
    return ParsedBatch(records=[RawReview(text=t, external_id=i) for t, i in zip(texts, ids)])


def test_ingest_creates_topic_source_and_scores(db_session):
    report = ingest_batch(
        db_session, "Pixel 9", "Amazon", _batch("Love it", "Great camera"),
        source_type=SourceType.ECOMMERCE, category="smartphones",
    )
    assert report.inserted == 2 and report.duplicates == 0 and report.rejected == 0
    assert report.topic.slug == "pixel-9"
    assert report.topic.category == "smartphones"
    assert report.source.name == "amazon"          # names are normalised to lower-case
    assert report.breakdown is not None and report.breakdown.score is not None
    assert all(r.analyzed_at is not None for r in db_session.query(Review).all())


def test_reingesting_same_reviews_inserts_nothing(db_session):
    ingest_batch(db_session, "Pixel 9", "amazon", _batch("Love it", "Great camera"))
    report = ingest_batch(db_session, "Pixel 9", "amazon", _batch("Love it", "  love   IT "))
    assert report.inserted == 0
    assert report.duplicates == 2
    assert db_session.query(Review).count() == 2


def test_duplicates_inside_one_batch_are_skipped(db_session):
    report = ingest_batch(db_session, "Pixel 9", "amazon", _batch("Love it", "Love it", "Meh"))
    assert report.inserted == 2
    assert report.duplicates == 1


def test_same_external_id_from_same_source_is_a_duplicate(db_session):
    ingest_batch(db_session, "Pixel 9", "amazon", _batch("Love it", ids=["r1"]))
    report = ingest_batch(db_session, "Pixel 9", "amazon", _batch("Edited: love it a lot", ids=["r1"]))
    assert report.inserted == 0 and report.duplicates == 1


def test_topic_lookup_ignores_case_and_spacing(db_session):
    a = get_or_create_topic(db_session, "Pixel 9")
    b = get_or_create_topic(db_session, "  pixel 9 ")
    assert a.id == b.id
    assert db_session.query(Topic).count() == 1


def test_existing_source_keeps_its_settings(db_session):
    get_or_create_source(db_session, "tech-news", SourceType.NEWS, weight=1.5)
    again = get_or_create_source(db_session, "TECH-NEWS", SourceType.OTHER, weight=1.0)
    assert again.weight == 1.5
    assert again.source_type is SourceType.NEWS
    assert db_session.query(Source).count() == 1


def test_parse_errors_are_carried_into_the_report(db_session):
    batch = ParsedBatch(records=[RawReview(text="Fine")], errors=[RowError(3, "Review text is missing")])
    report = ingest_batch(db_session, "Pixel 9", "amazon", batch)
    assert report.received == 2
    assert report.inserted == 1
    assert report.rejected == 1
    assert report.errors[0].row == 3


def test_ingest_without_recompute(db_session):
    report = ingest_batch(db_session, "Pixel 9", "amazon", _batch("Love it"), recompute=False)
    assert report.breakdown is None
    assert report.topic.sentiment_score is None


def test_sample_dataset_loads_once(db_session):
    first = load_sample_dataset(db_session)
    assert len(first) == 4
    assert all(r.inserted_reviews > 0 and r.inserted_ratings > 0 for r in first)
    assert db_session.query(Source).count() == 3
    review_count = db_session.query(Review).count()
    rating_count = db_session.query(UserRating).count()

    second = load_sample_dataset(db_session)
    assert all(r.inserted_reviews == 0 and r.inserted_ratings == 0 for r in second)
    assert db_session.query(Review).count() == review_count
    assert db_session.query(UserRating).count() == rating_count


def test_sample_dataset_scores_are_sensible(db_session):
    scores = {r.topic.name: r.breakdown.score for r in load_sample_dataset(db_session)}
    assert all(0 <= s <= 100 for s in scores.values())
    assert scores["Pixel 9"] > scores["Budget Earbuds X"] > scores["CrashyApp 2.0"]

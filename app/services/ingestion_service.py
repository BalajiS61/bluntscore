"""One ingestion pipeline for every source: validate -> de-duplicate -> store -> rescore."""
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.adapters import ParsedBatch, RawReview, RowError
from app.models import Review, Source, SourceType, Topic, UserRating
from app.models.mixins import utcnow
from app.scoring.engine import ScoreBreakdown
from app.services.scoring_service import recompute_topic_score
from app.utils.text import content_hash, slugify

SAMPLE_DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_reviews.json"


@dataclass
class IngestionReport:
    topic: Topic
    source: Source
    received: int
    inserted: int
    duplicates: int
    rejected: int
    errors: List[RowError] = field(default_factory=list)
    breakdown: Optional[ScoreBreakdown] = None


@dataclass
class SampleTopicResult:
    topic: Topic
    inserted_reviews: int
    inserted_ratings: int
    breakdown: ScoreBreakdown


# ---------- lookups ----------

def get_or_create_topic(
    db: Session, name: str, category: Optional[str] = None, description: Optional[str] = None
) -> Topic:
    name = (name or "").strip()
    if not name:
        raise ValueError("Topic name cannot be empty")
    topic = db.scalar(select(Topic).where(Topic.slug == slugify(name)))
    if topic is None:
        topic = Topic(name=name, category=category, description=description)
        db.add(topic)
        db.flush()
    elif category and not topic.category:
        topic.category = category
    return topic


def get_or_create_source(
    db: Session,
    name: str,
    source_type: SourceType = SourceType.OTHER,
    weight: float = 1.0,
    description: Optional[str] = None,
) -> Source:
    name = (name or "").strip().lower()
    if not name:
        raise ValueError("Source name cannot be empty")
    source = db.scalar(select(Source).where(Source.name == name))
    if source is None:
        source = Source(name=name, source_type=source_type, weight=weight, description=description)
        db.add(source)
        db.flush()
    return source


# ---------- main pipeline ----------

def ingest_batch(
    db: Session,
    topic_name: str,
    source_name: str,
    batch: ParsedBatch,
    source_type: SourceType = SourceType.OTHER,
    category: Optional[str] = None,
    recompute: bool = True,
) -> IngestionReport:
    """Store new reviews for one topic from one source and (optionally) rescore the topic.

    Duplicates are skipped, not errors: same text already on this topic, or the same
    external_id already seen from this source (including repeats inside this batch).
    """
    topic = get_or_create_topic(db, topic_name, category)
    source = get_or_create_source(db, source_name, source_type)

    seen_hashes = set(db.scalars(select(Review.content_hash).where(Review.topic_id == topic.id)))
    seen_external_ids = set(
        db.scalars(
            select(Review.external_id).where(
                Review.source_id == source.id, Review.external_id.is_not(None)
            )
        )
    )

    inserted = duplicates = 0
    for record in batch.records:
        digest = content_hash(record.text)
        if digest in seen_hashes or (record.external_id and record.external_id in seen_external_ids):
            duplicates += 1
            continue
        db.add(
            Review(
                topic=topic,
                source=source,
                text=record.text,
                author=record.author,
                external_id=record.external_id,
                published_at=record.published_at,
            )
        )
        seen_hashes.add(digest)
        if record.external_id:
            seen_external_ids.add(record.external_id)
        inserted += 1
    db.commit()

    breakdown = recompute_topic_score(db, topic) if recompute else None
    return IngestionReport(
        topic=topic,
        source=source,
        received=batch.received,
        inserted=inserted,
        duplicates=duplicates,
        rejected=len(batch.errors),
        errors=list(batch.errors),
        breakdown=breakdown,
    )


# ---------- bundled sample dataset ----------

def load_sample_dataset(
    db: Session, path: Path = SAMPLE_DATASET_PATH, now: Optional[datetime] = None
) -> List[SampleTopicResult]:
    """Load the demo dataset. Safe to run repeatedly: existing reviews/ratings are skipped."""
    now = now or utcnow()
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    for s in data["sources"]:
        get_or_create_source(
            db, s["name"], SourceType(s["source_type"]), s.get("weight", 1.0), s.get("description")
        )
    db.commit()

    results: List[SampleTopicResult] = []
    for t in data["topics"]:
        topic = get_or_create_topic(db, t["name"], t.get("category"), t.get("description"))
        db.commit()

        by_source = defaultdict(list)
        for r in t["reviews"]:
            by_source[r["source"]].append(
                RawReview(
                    text=r["text"],
                    author=r.get("author"),
                    published_at=now - timedelta(days=r.get("days_ago", 0)),
                )
            )

        inserted_reviews = 0
        for source_name, records in by_source.items():
            report = ingest_batch(db, topic.name, source_name, ParsedBatch(records=records), recompute=False)
            inserted_reviews += report.inserted

        existing_users = set(
            db.scalars(select(UserRating.user_id).where(UserRating.topic_id == topic.id))
        )
        inserted_ratings = 0
        for i, stars in enumerate(t.get("ratings", []), start=1):
            user_id = f"sample_user_{i}"
            if user_id not in existing_users:
                db.add(UserRating(topic=topic, user_id=user_id, rating=stars))
                inserted_ratings += 1
        db.commit()

        results.append(
            SampleTopicResult(topic, inserted_reviews, inserted_ratings, recompute_topic_score(db, topic))
        )
    return results

"""Queries behind the topic endpoints: search, details, reviews and summaries."""
from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ConflictError, NotFoundError
from app.models import Review, SentimentLabel, Source, Topic, UserRating
from app.utils.text import slugify

TOPIC_SORTS = {
    "-score": (Topic.sentiment_score.is_(None), Topic.sentiment_score.desc()),
    "score": (Topic.sentiment_score.is_(None), Topic.sentiment_score.asc()),
    "name": (Topic.name.asc(),),
    "-name": (Topic.name.desc(),),
    "-reviews": (Topic.review_count.desc(),),
    "reviews": (Topic.review_count.asc(),),
    "recent": (Topic.created_at.desc(),),
}

_review_time = func.coalesce(Review.published_at, Review.created_at)
REVIEW_SORTS = {
    "recent": (_review_time.desc(),),
    "oldest": (_review_time.asc(),),
    "-compound": (Review.sentiment_compound.is_(None), Review.sentiment_compound.desc()),
    "compound": (Review.sentiment_compound.is_(None), Review.sentiment_compound.asc()),
}


def _count(db: Session, stmt) -> int:
    return db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))


# ---------- topics ----------

def get_topic_by_slug(db: Session, slug: str) -> Topic:
    topic = db.scalar(select(Topic).where(Topic.slug == slug.strip().lower()))
    if topic is None:
        raise NotFoundError(f"Topic '{slug}' not found")
    return topic


def create_topic(db: Session, name: str, category: Optional[str], description: Optional[str]) -> Topic:
    slug = slugify(name)
    if db.scalar(select(Topic.id).where(Topic.slug == slug)) is not None:
        raise ConflictError(f"Topic '{name}' already exists (slug '{slug}')")
    topic = Topic(name=name, category=category or None, description=description or None)
    db.add(topic)
    db.commit()
    return topic


def delete_topic(db: Session, topic: Topic) -> None:
    db.delete(topic)
    db.commit()


def search_topics(
    db: Session,
    q: Optional[str] = None,
    category: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    sort: str = "-score",
    limit: int = 20,
    offset: int = 0,
) -> Tuple[List[Topic], int]:
    stmt = select(Topic)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Topic.name.ilike(pattern),
                Topic.slug.ilike(pattern),
                Topic.category.ilike(pattern),
                Topic.description.ilike(pattern),
            )
        )
    if category and category.strip():
        stmt = stmt.where(func.lower(Topic.category) == category.strip().lower())
    if min_score is not None:
        stmt = stmt.where(Topic.sentiment_score >= min_score)
    if max_score is not None:
        stmt = stmt.where(Topic.sentiment_score <= max_score)

    total = _count(db, stmt)
    items = db.scalars(stmt.order_by(*TOPIC_SORTS[sort], Topic.id).limit(limit).offset(offset)).all()
    return list(items), total


def source_count(db: Session, topic_id: int) -> int:
    return db.scalar(
        select(func.count(func.distinct(Review.source_id))).where(Review.topic_id == topic_id)
    )


# ---------- ratings stats ----------

def rating_stats(db: Session, topic_id: int) -> Tuple[int, Optional[float], dict]:
    rows = db.execute(
        select(UserRating.rating, func.count())
        .where(UserRating.topic_id == topic_id)
        .group_by(UserRating.rating)
    ).all()
    distribution = {str(stars): 0 for stars in range(1, 6)}
    for stars, n in rows:
        distribution[str(stars)] = n
    count = sum(distribution.values())
    average = round(sum(int(k) * v for k, v in distribution.items()) / count, 2) if count else None
    return count, average, distribution


# ---------- reviews ----------

def list_reviews(
    db: Session,
    topic: Topic,
    label: Optional[SentimentLabel] = None,
    source: Optional[str] = None,
    sort: str = "recent",
    limit: int = 20,
    offset: int = 0,
) -> Tuple[List[Review], int]:
    stmt = select(Review).join(Source).where(Review.topic_id == topic.id)
    if label is not None:
        stmt = stmt.where(Review.sentiment_label == label)
    if source and source.strip():
        stmt = stmt.where(Source.name == source.strip().lower())
    total = _count(db, stmt)
    items = db.scalars(
        stmt.options(selectinload(Review.source))
        .order_by(*REVIEW_SORTS[sort], Review.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return list(items), total


def top_reviews(db: Session, topic: Topic, label: SentimentLabel, limit: int = 3) -> List[Review]:
    order = (
        Review.sentiment_compound.desc() if label is SentimentLabel.POSITIVE
        else Review.sentiment_compound.asc()
    )
    return list(
        db.scalars(
            select(Review)
            .join(Source)
            .where(
                Review.topic_id == topic.id,
                Review.sentiment_label == label,
                Source.is_active == True,  # noqa: E712
            )
            .options(selectinload(Review.source))
            .order_by(order, Review.id)
            .limit(limit)
        ).all()
    )


def source_breakdown(db: Session, topic: Topic) -> List[dict]:
    rows = db.execute(
        select(
            Source.id,
            Source.name,
            Source.source_type,
            Source.weight,
            Source.is_active,
            Review.sentiment_label,
            func.count(Review.id),
            func.avg(Review.sentiment_compound),
        )
        .join(Review, Review.source_id == Source.id)
        .where(Review.topic_id == topic.id)
        .group_by(
            Source.id, Source.name, Source.source_type, Source.weight, Source.is_active,
            Review.sentiment_label,
        )
        .order_by(Source.name)
    ).all()

    summaries: dict[int, dict] = {}
    for source_id, name, source_type, weight, is_active, label, n, avg in rows:
        s = summaries.setdefault(
            source_id,
            {
                "source": name, "source_type": source_type, "weight": weight, "is_active": is_active,
                "review_count": 0, "positive": 0, "neutral": 0, "negative": 0,
                "_sum": 0.0, "_scored": 0,
            },
        )
        s["review_count"] += n
        if label is not None:
            s[label.value] += n
        if avg is not None:
            s["_sum"] += avg * n
            s["_scored"] += n

    result = []
    for s in summaries.values():
        s["average_compound"] = round(s["_sum"] / s["_scored"], 4) if s["_scored"] else None
        del s["_sum"], s["_scored"]
        result.append(s)
    return result


def build_headline(verdict: str, score: Optional[float], counts: dict, total: int, sources: int) -> str:
    if total == 0:
        return "No reviews yet"
    pct = {k: round(v / total * 100) for k, v in counts.items()}
    score_text = f"{score:.1f}/100" if score is not None else "no score"
    plural = "source" if sources == 1 else "sources"
    return (
        f"{verdict} ({score_text}): {pct['positive']}% positive, {pct['neutral']}% neutral, "
        f"{pct['negative']}% negative across {total} reviews from {sources} {plural}"
    )

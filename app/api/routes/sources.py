"""Source endpoints: see where reviews come from and tune how much each source counts."""
from typing import List

from fastapi import APIRouter, Depends, Path
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.database import get_db
from app.models import Review, Source, Topic
from app.schemas.common import error_responses
from app.schemas.sources import SourceOut, SourceUpdate, SourceUpdateOut
from app.services.scoring_service import recompute_topic_score

router = APIRouter(prefix="/sources", tags=["Sources"])


def _review_count(db: Session, source_id: int) -> int:
    return db.scalar(select(func.count(Review.id)).where(Review.source_id == source_id))


@router.get("", response_model=List[SourceOut], summary="List all review sources")
def list_sources(db: Session = Depends(get_db)) -> List[SourceOut]:
    rows = db.execute(
        select(Source, func.count(Review.id))
        .outerjoin(Review, Review.source_id == Source.id)
        .group_by(Source.id)
        .order_by(Source.name)
    ).all()
    return [SourceOut.build(source, count) for source, count in rows]


@router.patch("/{name}", response_model=SourceUpdateOut, summary="Update a source and rescore affected topics",
              responses=error_responses(404))
def update_source(
    payload: SourceUpdate,
    name: str = Path(..., min_length=1, max_length=80),
    db: Session = Depends(get_db),
) -> SourceUpdateOut:
    source = db.scalar(select(Source).where(Source.name == name.strip().lower()))
    if source is None:
        raise NotFoundError(f"Source '{name}' not found")

    changes = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    for field, value in changes.items():
        setattr(source, field, value)
    db.commit()

    rescored = 0
    if {"weight", "is_active"} & changes.keys():
        topic_ids = db.scalars(
            select(Review.topic_id).where(Review.source_id == source.id).distinct()
        ).all()
        for topic in db.scalars(select(Topic).where(Topic.id.in_(topic_ids))).all():
            recompute_topic_score(db, topic)
            rescored += 1

    return SourceUpdateOut(source=SourceOut.build(source, _review_count(db, source.id)), rescored_topics=rescored)

"""Bulk score maintenance."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import Topic
from app.schemas.topics import RefreshAllOut, RefreshedTopic
from app.services.scoring_service import recompute_topic_score

router = APIRouter(prefix="/scores", tags=["Scores"])


@router.post("/refresh", response_model=RefreshAllOut, summary="Re-analyze and rescore every topic")
def refresh_all(db: Session = Depends(get_db)) -> RefreshAllOut:
    refreshed = []
    for topic in db.scalars(select(Topic).order_by(Topic.name)).all():
        b = recompute_topic_score(db, topic)
        refreshed.append(RefreshedTopic(slug=topic.slug, name=topic.name, score=b.score, verdict=b.verdict))
    return RefreshAllOut(rescored=len(refreshed), topics=refreshed)

"""Shared route dependencies."""
from fastapi import Depends, Path
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import Topic
from app.services.topic_service import get_topic_by_slug


def topic_from_path(
    slug: str = Path(..., min_length=1, max_length=140, description="Topic slug, e.g. pixel-9"),
    db: Session = Depends(get_db),
) -> Topic:
    """Resolves {slug} in the URL to a Topic, or returns a 404 error."""
    return get_topic_by_slug(db, slug)

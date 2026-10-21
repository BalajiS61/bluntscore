"""User rating endpoints. Every change immediately updates the topic's score."""
from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import topic_from_path
from app.db.database import get_db
from app.models import Topic
from app.schemas.common import error_responses
from app.schemas.ratings import RatingIn, RatingOut, RatingSubmitOut, RatingSummaryOut
from app.services import rating_service, topic_service
from app.services.scoring_service import recompute_topic_score

router = APIRouter(prefix="/topics/{slug}/ratings", tags=["Ratings"], responses=error_responses(404))


@router.post(
    "",
    response_model=RatingSubmitOut,
    status_code=status.HTTP_201_CREATED,
    summary="Rate a topic (1-5 stars); rating again updates it",
    responses={200: {"description": "Existing rating updated"}, 201: {"description": "New rating created"}},
)
def submit_rating(
    payload: RatingIn,
    response: Response,
    topic: Topic = Depends(topic_from_path),
    db: Session = Depends(get_db),
) -> RatingSubmitOut:
    rating, created = rating_service.upsert_rating(db, topic, payload.user_id, payload.rating, payload.comment)
    if not created:
        response.status_code = status.HTTP_200_OK
    breakdown = recompute_topic_score(db, topic)
    return RatingSubmitOut(
        created=created,
        rating=RatingOut.model_validate(rating),
        topic_score=breakdown.score,
        verdict=breakdown.verdict,
    )


@router.get("", response_model=RatingSummaryOut, summary="Aggregate user ratings for a topic")
def get_ratings(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    topic: Topic = Depends(topic_from_path),
    db: Session = Depends(get_db),
) -> RatingSummaryOut:
    count, average, distribution = topic_service.rating_stats(db, topic.id)
    return RatingSummaryOut(
        topic_slug=topic.slug,
        count=count,
        average=average,
        distribution=distribution,
        items=[RatingOut.model_validate(r) for r in rating_service.list_ratings(db, topic, limit, offset)],
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a user's rating")
def delete_rating(
    user_id: str = Path(..., min_length=1, max_length=80),
    topic: Topic = Depends(topic_from_path),
    db: Session = Depends(get_db),
) -> Response:
    rating_service.delete_rating(db, topic, user_id)
    recompute_topic_score(db, topic)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

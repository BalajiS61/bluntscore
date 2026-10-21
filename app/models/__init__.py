"""Import every model here so Base.metadata knows about all tables."""
from app.models.enums import SentimentLabel, SourceType
from app.models.review import Review
from app.models.source import Source
from app.models.topic import Topic
from app.models.user_rating import UserRating

__all__ = ["Topic", "Source", "Review", "UserRating", "SentimentLabel", "SourceType"]

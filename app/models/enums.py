"""Enumerations shared by models and (later) API schemas."""
import enum

from sqlalchemy import Enum as SAEnum


class SentimentLabel(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class SourceType(str, enum.Enum):
    SOCIAL = "social"
    ECOMMERCE = "ecommerce"
    NEWS = "news"
    FORUM = "forum"
    SURVEY = "survey"
    OTHER = "other"


def enum_column(enum_cls: type[enum.Enum], length: int = 20) -> SAEnum:
    """Store enums as their plain string values, with validation."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )

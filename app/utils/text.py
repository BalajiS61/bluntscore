"""Small text helpers shared across the app."""
import hashlib
import re
import unicodedata


def slugify(value: str) -> str:
    """'Apple iPhone 16 Pro!' -> 'apple-iphone-16-pro'."""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "topic"


def normalize_text(text: str) -> str:
    """Lower-case and collapse whitespace so near-identical texts compare equal."""
    return re.sub(r"\s+", " ", text).strip().lower()


def content_hash(text: str) -> str:
    """SHA-256 of the normalized text, used to detect duplicate reviews."""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()

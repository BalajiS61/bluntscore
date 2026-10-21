"""Text cleaning applied before sentiment analysis.

VADER uses capitalisation, punctuation (!!!) and emojis as sentiment signals,
so we deliberately do NOT lower-case text or strip punctuation/emojis.
We only remove noise that carries no opinion: HTML, URLs, @mentions.
"""
import html
import re

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_MENTION_RE = re.compile(r"(?<!\w)@\w+")
_HASHTAG_RE = re.compile(r"(?<!\w)#(\w+)")
_ELONGATED_RE = re.compile(r"([A-Za-z])\1{2,}")
_WHITESPACE_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """'<b>Sooooo GOOD</b> http://x.co @bob #love' -> 'Soo GOOD love'."""
    if not text:
        return ""
    text = html.unescape(text)
    text = _TAG_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    text = _MENTION_RE.sub(" ", text)
    text = _HASHTAG_RE.sub(r"\1", text)
    text = _ELONGATED_RE.sub(r"\1\1", text)  # "goooood" -> "good"
    return _WHITESPACE_RE.sub(" ", text).strip()

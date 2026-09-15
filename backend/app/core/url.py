from __future__ import annotations

from urllib.parse import urlsplit

ALLOWED_SCHEMES = {"http", "https"}
MAX_URL_LENGTH = 2048


def normalize_url(url: str) -> str:
    return url.strip()


def is_valid_url(url: str) -> bool:
    """True for a well-formed http(s) URL with a non-empty host."""
    if not url or len(url) > MAX_URL_LENGTH:
        return False
    parts = urlsplit(url)
    return parts.scheme in ALLOWED_SCHEMES and bool(parts.netloc)

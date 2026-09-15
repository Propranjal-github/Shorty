from __future__ import annotations


class ShortyError(Exception):
    """Base class for all domain errors raised by the application."""


class NotFoundError(ShortyError):
    """Raised when a referenced resource does not exist."""


class ConflictError(ShortyError):
    """Raised on a uniqueness or state conflict."""


class InvalidUrlError(ShortyError):
    """Raised when a submitted URL is malformed or disallowed."""


class RateLimitExceededError(ShortyError):
    """Raised when a caller has exceeded its rate budget."""


class ClockMovedBackwardsError(ShortyError):
    """Raised by the snowflake generator when the system clock regresses."""

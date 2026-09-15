from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.url import is_valid_url, normalize_url


class URLRequest(BaseModel):
    url: str = Field(..., description="The URL to shorten.")
    custom_code: str | None = Field(default=None, max_length=16, pattern=r"^[A-Za-z0-9_-]{1,16}$")
    ttl_seconds: int | None = Field(default=None, ge=1, le=31_536_000)

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        normalized = normalize_url(value)
        if not is_valid_url(normalized):
            raise ValueError("must be a valid http(s) URL")
        return normalized


class URLResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    short_code: str
    short_url: str
    original_url: str
    created_at: datetime
    expires_at: datetime | None


class URLStats(BaseModel):
    short_code: str
    original_url: str
    click_count: int
    created_at: datetime
    expires_at: datetime | None


class ClickBucket(BaseModel):
    bucket: datetime
    clicks: int


class ReferrerCount(BaseModel):
    referrer: str | None
    count: int


class AnalyticsResponse(BaseModel):
    short_code: str
    total_clicks: int
    recent: list[ClickBucket]
    top_referrers: list[ReferrerCount]

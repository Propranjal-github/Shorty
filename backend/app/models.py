from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class URLRecord(Base):
    """A shortened URL mapping: a unique short code -> original URL."""

    __tablename__ = "urls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    short_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    original_url: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    click_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return f"<URL {self.short_code} -> {self.original_url[:40]}>"


class ClickEvent(Base):
    """A single redirect click, written in batches by the analytics flusher."""

    __tablename__ = "click_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    short_code: Mapped[str] = mapped_column(
        String(16), ForeignKey("urls.short_code", ondelete="CASCADE"), index=True
    )
    clicked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    referrer: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)


class MachineIdLease(Base):
    """A snowflake machine_id held by a live instance.

    The unique PK guarantees no two instances share a machine_id simultaneously;
    expired rows are reaped on the next lease attempt. This is what keeps
    snowflake IDs collision-free when Cloud Run autoscales to many instances.
    """

    __tablename__ = "machine_id_leases"

    machine_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)

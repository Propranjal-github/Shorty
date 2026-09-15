from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


_connect_args = (
    # check_same_thread=False lets the request session share the engine across
    # threads; timeout (busy-timeout, seconds) makes concurrent writers wait for
    # the SQLite write lock instead of failing with "database is locked".
    {"check_same_thread": False, "timeout": 30}
    if settings.database_url.startswith("sqlite")
    else {}
)
engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create all tables. Imports models to ensure they are registered on the base."""
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a scoped DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

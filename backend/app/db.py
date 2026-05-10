from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_env


class Base(DeclarativeBase):
    pass


def _normalise_db_url(url: str) -> str:
    """Supabase / Heroku style 'postgres://...' → SQLAlchemy psycopg3 driver.

    SQLAlchemy 2.x does not accept the bare 'postgres://' scheme; we route it
    through psycopg3 explicitly. SQLite urls are returned untouched.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


_db_url = _normalise_db_url(get_env().database_url)
_is_sqlite = _db_url.startswith("sqlite")
_engine = create_engine(
    _db_url,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # On Postgres, lighten the connection pool (Supabase free tier limits).
    pool_pre_ping=not _is_sqlite,
    pool_size=5 if not _is_sqlite else 0,
    max_overflow=5 if not _is_sqlite else 0,
)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    from . import models  # noqa: F401  ensure models are registered
    Base.metadata.create_all(bind=_engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Session:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

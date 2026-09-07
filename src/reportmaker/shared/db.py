"""Database connection management using SQLAlchemy."""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_sessionmaker: sessionmaker | None = None


def get_engine() -> Engine:
    """Return a singleton SQLAlchemy engine."""
    global _engine
    if _engine is None:
        database_url = os.getenv("DATABASE_URL", "sqlite:///reportmaker.db")
        _engine = create_engine(
            database_url,
            pool_pre_ping=True,
            echo=bool(os.getenv("SQL_ECHO", False)),
        )
    return _engine


def get_sessionmaker() -> sessionmaker:
    """Return a sessionmaker bound to the engine."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return _sessionmaker


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager for a database session."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

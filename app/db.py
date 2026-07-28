"""
Database engine and session setup.

Defaults to a local SQLite file so you can build and test everything with
zero setup. When you're ready to deploy, just set DATABASE_URL in .env to
your Neon (or other Postgres) connection string - no code changes needed.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    # Needed for SQLite to work with FastAPI's multi-threaded request handling
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency - yields a DB session and always closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Safe to call every startup - no-ops if they exist."""
    from app import models  # noqa: F401 - ensures models are registered on Base
    Base.metadata.create_all(bind=engine)

"""Database Engine, Session Management, and Deterministic Table Initialization.

Supports SQLite persistent storage with thread-safe connection pooling,
safe directory provisioning, and clean isolation for test suites.
"""

from pathlib import Path
from typing import Generator, Optional
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base

# Active global engine and sessionmaker
_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def get_engine(database_url: Optional[str] = None) -> Engine:
    """Retrieve or create the SQLAlchemy engine with safe SQLite configuration."""
    global _engine, _session_factory
    url = database_url or settings.database_url

    # If already initialized for this URL, return cached engine
    if _engine is not None and str(_engine.url) == url:
        return _engine

    # Ensure parent directory exists if using local SQLite file
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        db_path_str = url.replace("sqlite:///", "")
        db_path = Path(db_path_str).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)

    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    _engine = create_engine(
        url,
        connect_args=connect_args,
        echo=False,
    )
    _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_session_factory(database_url: Optional[str] = None) -> sessionmaker:
    """Get the active sessionmaker."""
    global _session_factory, _engine
    url = database_url or settings.database_url
    if _session_factory is None or _engine is None or str(_engine.url) != url:
        get_engine(url)
    return _session_factory


# Session factory convenience alias
def SessionLocal() -> Session:
    return get_session_factory()()


def init_db(engine: Optional[Engine] = None) -> None:
    """Create all registered database tables deterministically."""
    target_engine = engine or get_engine()
    Base.metadata.create_all(bind=target_engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a transactional SQLAlchemy session."""
    session_factory = get_session_factory()
    db: Session = session_factory()
    try:
        yield db
    finally:
        db.close()

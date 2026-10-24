"""FastAPI Dependency Injection Providers.

Provides dependencies for database sessions, repository access, and services.
"""

from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.repository import Repository
from app.db.session import get_db


def get_repository(db: Session = Depends(get_db)) -> Repository:
    """Dependency injecting initialized domain Repository."""
    return Repository(db)

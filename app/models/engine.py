from sqlalchemy.engine import Engine
from sqlmodel import Session as SQLSession
from sqlmodel import create_engine

from app.core.settings import settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings.ensure_db_dir()
        _engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})
    return _engine


def get_session() -> SQLSession:
    """Return a new SQLModel Session. Caller is responsible for closing it."""
    return SQLSession(get_engine())

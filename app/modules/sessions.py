from datetime import UTC, datetime

from sqlmodel import col, select

from app.models.engine import get_session
from app.models.models import Session


def create_session(session_id: str, title: str, project_path: str) -> Session:
    row = Session(id=session_id, title=title, project_path=project_path)
    db = get_session()
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    finally:
        db.close()
    return row


def list_sessions() -> list[Session]:
    db = get_session()
    try:
        stmt = select(Session).order_by(col(Session.updated_at).desc())
        return list(db.exec(stmt).all())
    finally:
        db.close()


def get_session_row(session_id: str) -> Session | None:
    db = get_session()
    try:
        return db.get(Session, session_id)
    finally:
        db.close()


def touch_session(session_id: str) -> None:
    db = get_session()
    try:
        row = db.get(Session, session_id)
        if row is None:
            return
        row.updated_at = datetime.now(UTC)
        db.add(row)
        db.commit()
    finally:
        db.close()

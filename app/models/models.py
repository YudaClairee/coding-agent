from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Session(SQLModel, table=True):
    __tablename__ = "sessions"

    id: str = Field(primary_key=True)
    title: str
    project_path: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine():
    settings = get_settings()
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)


engine = _engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_engine() -> None:
    """Rebuild engine after settings change (tests)."""
    global engine, SessionLocal
    engine.dispose()
    engine = _engine()
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def is_postgres(bind=None) -> bool:
    target = bind or engine
    return target.dialect.name == "postgresql"


def ensure_pgvector(bind=None) -> None:
    """Create pgvector extension and embedding column on PostgreSQL only."""
    target = bind or engine
    if not is_postgres(target):
        return
    settings = get_settings()
    dim = int(settings.embedding_dim)
    with target.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(
            text(
                f"ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector({dim})"
            )
        )

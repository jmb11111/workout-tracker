from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

from app.core.config import settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10)


def get_session_factory():
    return sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)


# Convenience aliases for direct use
def SessionLocal():
    return get_session_factory()()


def get_db():
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()

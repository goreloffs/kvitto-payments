from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# SQLite требует особый флаг для многопоточности (uvicorn работает в потоках).
# Для других СУБД connect_args не нужен.
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,  # поставь True, если хочешь видеть все SQL-запросы в консоли
)


# База для всех ORM-моделей (SQLAlchemy 2.0-стиль).
class Base(DeclarativeBase):
    pass


# Фабрика сессий. autocommit/autoflush выключены явно — управляем вручную.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI-зависимость: одна сессия на запрос, гарантированно закрывается."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

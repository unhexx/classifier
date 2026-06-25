"""
Управление подключением к БД (SQLite).

Для простоты и максимальной совместимости на старте используем
синхронный SQLAlchemy (отлично работает с uvicorn + workers).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models import Base

# Для SQLite важно: check_same_thread=False при использовании в нескольких потоках
connect_args = {"check_same_thread": False} if "sqlite" in settings.database_url else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,  # Поменять на True при отладке SQL
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)


def init_db() -> None:
    """Создаёт таблицы и применяет миграции."""
    from app.db.migrations import run_migrations

    run_migrations()


def get_db():
    """Генератор сессий для зависимостей FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""Общие фикстуры для тестов."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.seeds import ensure_catalogs_loaded


@pytest.fixture(scope="session")
def test_engine():
    """In-memory SQLite для быстрых тестов."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db_session(test_engine):
    """Свежая сессия + загруженные сиды."""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    # Прямой init таблиц + seed (используем основной путь к сидам)
    Base.metadata.create_all(test_engine)
    ensure_catalogs_loaded(session)
    yield session
    session.close()

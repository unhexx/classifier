"""
Простые миграции схемы SQLite (без Alembic).

Добавляет новые таблицы и колонки при обновлении версии.
"""

from sqlalchemy import inspect, text

from app.db.models import Base
from app.db.session import engine


def _column_exists(table: str, column: str) -> bool:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def run_migrations() -> None:
    """Применяет инкрементальные изменения схемы."""
    Base.metadata.create_all(bind=engine)

    migrations: list[tuple[str, str, str]] = [
        ("classification_logs", "original_context", "TEXT"),
        ("classification_logs", "pd_entities_json", "TEXT"),
        ("faults", "failure_mode", "TEXT"),
    ]

    with engine.begin() as conn:
        for table, column, col_type in migrations:
            if not _column_exists(table, column):
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))

        # Новые таблицы создаются через create_all выше
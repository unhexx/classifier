"""
SQLAlchemy ORM модели.

Храним справочники и типовые неисправности в SQLite.
Используем современный стиль SQLAlchemy 2.0 (Mapped).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


class Catalog(Base):
    """Справочник (набор типовых неисправностей)."""

    __tablename__ = "catalogs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(16), default="1.0", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Связь будет через явные запросы (для простоты на старте)


class Fault(Base):
    """
    Типовая неисправность.

    Поля symptoms и keywords хранятся как JSON-списки (SQLite поддерживает).
    """

    __tablename__ = "faults"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    catalog_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    code: Mapped[str] = mapped_column(String(32), nullable=False)  # SRV-DISK-001 и т.п.
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Списки строк
    symptoms: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recommended_actions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    # Произвольные метаданные (модель оборудования, версии и т.д.)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Естественный уникальный ключ внутри каталога
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class ClassificationLog(Base):
    """Журнал классификаций для аудита и отладки."""

    __tablename__ = "classification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    catalog_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)
    original_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    pd_entities_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    top_matches_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    top_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    processing_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PdCleaningLog(Base):
    """Журнал очистки персональных данных."""

    __tablename__ = "pd_cleaning_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_text: Mapped[str] = mapped_column(Text, nullable=False)
    entities_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    entity_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ControllerFeedback(Base):
    """Обратная связь контролёра для дообучения модели очистки ПД."""

    __tablename__ = "controller_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    model_output: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_text: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    missed_fragment: Mapped[str | None] = mapped_column(Text, nullable=True)
    controller_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LearnedPdPattern(Base):
    """Дообученное правило очистки ПД (из обратной связи контролёра)."""

    __tablename__ = "learned_pd_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    replacement: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)
    source_feedback_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

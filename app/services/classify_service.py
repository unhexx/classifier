"""
Сервисный слой классификации с аудитом и метриками.
"""

from sqlalchemy.orm import Session

from app.core.classifier import engine
from app.core.config import settings
from app.core.models import ClassifyRequest, ClassifyResponse, HistoryEntry
from app.db.models import ClassificationLog


def classify_context(db: Session, request: ClassifyRequest) -> ClassifyResponse:
    """Классифицирует контекст и при необходимости пишет в журнал."""
    result = engine.classify(request)

    if settings.enable_classification_logging and result.matches:
        top_conf = result.matches[0].confidence if result.matches else None
        log_entry = ClassificationLog(
            catalog_name=request.catalog.lower().strip(),
            context=result.context,
            top_matches_json=[m.model_dump() for m in result.matches],
            top_confidence=top_conf,
            processing_time_ms=result.processing_time_ms,
        )
        db.add(log_entry)
        db.commit()

    return result


def get_classification_history(db: Session, limit: int | None = None) -> list[HistoryEntry]:
    """Возвращает последние записи журнала классификаций."""
    max_entries = limit or settings.history_max_entries
    rows = (
        db.query(ClassificationLog)
        .order_by(ClassificationLog.created_at.desc())
        .limit(max_entries)
        .all()
    )
    return [
        HistoryEntry(
            id=row.id,
            catalog_name=row.catalog_name,
            context=row.context,
            top_matches=row.top_matches_json,
            top_confidence=row.top_confidence,
            processing_time_ms=row.processing_time_ms,
            created_at=row.created_at.isoformat() if row.created_at else "",
        )
        for row in rows
    ]
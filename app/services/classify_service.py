"""
Сервисный слой классификации с очисткой ПД, аудитом и метриками.
"""

from sqlalchemy.orm import Session

from app.core.classifier import engine
from app.core.config import settings
from app.core.models import ClassifyRequest, ClassifyResponse, HistoryEntry, PdEntityRead
from app.db.models import ClassificationLog
from app.services.pd_service import clean_text


def classify_context(db: Session, request: ClassifyRequest) -> ClassifyResponse:
    """Очищает ПД, классифицирует контекст и при необходимости пишет в журнал."""
    original_text = request.resolved_context_text()
    pd_entities: list[PdEntityRead] = []
    pd_time_ms: float | None = None
    cleaned_text = original_text
    pd_applied = False

    if settings.enable_pd_cleaning and not request.skip_pd_cleaning and original_text:
        pd_result = clean_text(db, original_text, log=False)
        cleaned_text = pd_result.cleaned_text
        pd_time_ms = pd_result.processing_time_ms
        pd_entities = [PdEntityRead(**e.__dict__) for e in pd_result.entities]
        pd_applied = len(pd_entities) > 0

    # Подменяем контекст на очищенный для классификации
    classify_req = request.model_copy(update={"context": cleaned_text})
    result = engine.classify(classify_req)

    response = ClassifyResponse(
        catalog=result.catalog,
        context=cleaned_text,
        original_context=original_text if pd_applied else None,
        pd_entities=pd_entities,
        pd_cleaning_applied=pd_applied,
        matches=result.matches,
        total_candidates=result.total_candidates,
        processing_time_ms=round((result.processing_time_ms or 0) + (pd_time_ms or 0), 2),
        scoring_time_ms=result.processing_time_ms,
        pd_cleaning_time_ms=pd_time_ms,
        scoring_weights=result.scoring_weights,
    )

    if settings.enable_classification_logging and response.matches:
        top_conf = response.matches[0].confidence if response.matches else None
        log_entry = ClassificationLog(
            catalog_name=request.catalog.lower().strip(),
            context=cleaned_text,
            original_context=original_text if pd_applied else None,
            pd_entities_json=[e.model_dump() for e in pd_entities] if pd_entities else None,
            top_matches_json=[m.model_dump() for m in response.matches],
            top_confidence=top_conf,
            processing_time_ms=response.processing_time_ms,
        )
        db.add(log_entry)
        db.commit()

    return response


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
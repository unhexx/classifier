"""
Сервис очистки персональных данных.
"""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import PdCleanRequest, PdCleanResponse, PdEntityRead
from app.core.pd_cleaner import PdCleaningResult, pd_cleaner
from app.db.models import LearnedPdPattern, PdCleaningLog


def _load_learned_patterns(db: Session) -> None:
    """Подгружает дообученные паттерны в модель."""
    rows = db.query(LearnedPdPattern).filter(LearnedPdPattern.active.is_(True)).all()
    patterns = [(r.entity_type, r.pattern, r.replacement, r.confidence) for r in rows]
    pd_cleaner.load_learned_patterns(patterns)


def clean_text(db: Session, text: str, log: bool = True) -> PdCleaningResult:
    """Очищает текст от ПД с учётом дообученных правил."""
    if settings.enable_pd_cleaning:
        _load_learned_patterns(db)
    result = pd_cleaner.clean(text)

    if log and settings.enable_pd_cleaning_log and result.entities:
        entry = PdCleaningLog(
            original_text=result.original_text,
            cleaned_text=result.cleaned_text,
            entities_json=[
                {
                    "entity_type": e.entity_type,
                    "original": e.original,
                    "replacement": e.replacement,
                    "start": e.start,
                    "end": e.end,
                    "confidence": e.confidence,
                }
                for e in result.entities
            ],
            entity_count=len(result.entities),
            processing_time_ms=result.processing_time_ms,
        )
        db.add(entry)
        db.commit()

    return result


def preview_clean(db: Session, request: PdCleanRequest) -> PdCleanResponse:
    """Предпросмотр очистки ПД (для UI контролёра)."""
    result = clean_text(db, request.text, log=request.save_log)
    return PdCleanResponse(
        original_text=result.original_text,
        cleaned_text=result.cleaned_text,
        entities=[PdEntityRead(**e.__dict__) for e in result.entities],
        entity_count=len(result.entities),
        processing_time_ms=result.processing_time_ms,
        model_version=result.model_version,
    )
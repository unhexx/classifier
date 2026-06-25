"""
Сервис дообучения модели очистки ПД на обратной связи контролёра.
"""

import json
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import FeedbackCreate, FeedbackEntry, TrainingExportResponse
from app.db.models import ControllerFeedback, LearnedPdPattern


def submit_feedback(db: Session, data: FeedbackCreate) -> FeedbackEntry:
    """Контролёр отправляет исправление ошибки модели очистки ПД."""
    entry = ControllerFeedback(
        original_text=data.original_text,
        model_output=data.model_output,
        corrected_text=data.corrected_text,
        entity_type=data.entity_type,
        missed_fragment=data.missed_fragment,
        controller_notes=data.controller_notes,
        status="pending",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _to_entry(entry)


def list_feedback(db: Session, status: str | None = None, limit: int = 50) -> list[FeedbackEntry]:
    """Список обратной связи для контроля дообучения."""
    q = db.query(ControllerFeedback).order_by(ControllerFeedback.created_at.desc())
    if status:
        q = q.filter(ControllerFeedback.status == status)
    rows = q.limit(limit).all()
    return [_to_entry(r) for r in rows]


def apply_feedback(db: Session, feedback_id: int) -> FeedbackEntry:
    """
    Применяет обратную связь: создаёт дообученное правило из пропущенного фрагмента.
    """
    entry = db.query(ControllerFeedback).filter(ControllerFeedback.id == feedback_id).first()
    if entry is None:
        raise ValueError(f"Запись обратной связи #{feedback_id} не найдена")
    if entry.status == "applied":
        raise ValueError(f"Запись #{feedback_id} уже применена")

    if entry.missed_fragment:
        escaped = re.escape(entry.missed_fragment.strip())
        pattern = LearnedPdPattern(
            entity_type=entry.entity_type or "custom",
            pattern=escaped,
            replacement=f"[{entry.entity_type.upper() if entry.entity_type else 'PD'}]",
            confidence=0.85,
            source_feedback_id=entry.id,
            active=True,
        )
        db.add(pattern)

    entry.status = "applied"
    db.commit()
    db.refresh(entry)
    return _to_entry(entry)


def export_training_data(db: Session) -> TrainingExportResponse:
    """Экспортирует данные для дообучения в JSONL."""
    rows = (
        db.query(ControllerFeedback)
        .filter(ControllerFeedback.status.in_(["pending", "applied"]))
        .order_by(ControllerFeedback.created_at.asc())
        .all()
    )
    lines = []
    for row in rows:
        record = {
            "original": row.original_text,
            "model_output": row.model_output,
            "corrected": row.corrected_text,
            "entity_type": row.entity_type,
            "missed_fragment": row.missed_fragment,
            "notes": row.controller_notes,
            "status": row.status,
        }
        lines.append(json.dumps(record, ensure_ascii=False))

    export_dir = settings.training_export_dir
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / "pd_feedback.jsonl"
    export_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    learned = db.query(LearnedPdPattern).filter(LearnedPdPattern.active.is_(True)).count()

    return TrainingExportResponse(
        export_path=str(export_path),
        feedback_count=len(rows),
        learned_patterns_count=learned,
        lines=lines,
    )


def _to_entry(row: ControllerFeedback) -> FeedbackEntry:
    return FeedbackEntry(
        id=row.id,
        original_text=row.original_text,
        model_output=row.model_output,
        corrected_text=row.corrected_text,
        entity_type=row.entity_type,
        missed_fragment=row.missed_fragment,
        controller_notes=row.controller_notes,
        status=row.status,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )
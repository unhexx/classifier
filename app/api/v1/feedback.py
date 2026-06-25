"""API обратной связи контролёра и дообучения."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.models import FeedbackCreate, FeedbackEntry, TrainingExportResponse
from app.db.session import get_db
from app.services import training_service

router = APIRouter(prefix="/api/v1/feedback", tags=["training"])


@router.post("", response_model=FeedbackEntry, status_code=201)
def submit_feedback(data: FeedbackCreate, db: Session = Depends(get_db)) -> FeedbackEntry:
    """Контролёр сообщает об ошибке очистки ПД."""
    return training_service.submit_feedback(db, data)


@router.get("", response_model=list[FeedbackEntry])
def list_feedback(
    status: str | None = Query(None, description="pending | applied | rejected"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[FeedbackEntry]:
    """Список обратной связи для контроля дообучения."""
    return training_service.list_feedback(db, status=status, limit=limit)


@router.post("/{feedback_id}/apply", response_model=FeedbackEntry)
def apply_feedback(feedback_id: int, db: Session = Depends(get_db)) -> FeedbackEntry:
    """Применить обратную связь — добавить дообученное правило."""
    try:
        return training_service.apply_feedback(db, feedback_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/export", response_model=TrainingExportResponse)
def export_training(db: Session = Depends(get_db)) -> TrainingExportResponse:
    """Экспорт данных для дообучения модели."""
    return training_service.export_training_data(db)
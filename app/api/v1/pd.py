"""API очистки персональных данных."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.models import PdCleanRequest, PdCleanResponse
from app.db.session import get_db
from app.services.pd_service import preview_clean

router = APIRouter(prefix="/api/v1/pd", tags=["pd-cleaning"])


@router.post("/clean", response_model=PdCleanResponse)
def clean_pd(request: PdCleanRequest, db: Session = Depends(get_db)) -> PdCleanResponse:
    """Предпросмотр очистки контекста от ПД (для контроля контролёром)."""
    return preview_clean(db, request)
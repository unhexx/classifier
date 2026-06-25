"""
Административные эндпоинты для управления справочниками.

Предназначены для доверенной локальной среды без аутентификации.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.models import FaultCreate, FaultRead, FaultUpdate
from app.db.session import get_db
from app.services import catalog_service

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _fault_to_read(fault) -> FaultRead:
    return FaultRead(
        code=fault.code,
        title=fault.title,
        description=fault.description,
        symptoms=fault.symptoms or [],
        keywords=fault.keywords or [],
        category=fault.category,
        recommended_actions=fault.recommended_actions or [],
        meta=fault.meta,
    )


@router.post(
    "/catalogs/{name}/faults",
    response_model=FaultRead,
    status_code=status.HTTP_201_CREATED,
)
def create_fault(name: str, data: FaultCreate, db: Session = Depends(get_db)) -> FaultRead:
    """Добавляет новую неисправность в справочник."""
    try:
        fault = catalog_service.add_fault(db, name, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _fault_to_read(fault)


@router.put("/catalogs/{name}/faults/{code}", response_model=FaultRead)
def update_fault(
    name: str, code: str, data: FaultUpdate, db: Session = Depends(get_db)
) -> FaultRead:
    """Обновляет существующую неисправность."""
    try:
        fault = catalog_service.update_fault(db, name, code, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _fault_to_read(fault)


@router.delete("/catalogs/{name}/faults/{code}", status_code=status.HTTP_204_NO_CONTENT)
def remove_fault(name: str, code: str, db: Session = Depends(get_db)) -> None:
    """Удаляет неисправность из справочника."""
    try:
        catalog_service.delete_fault(db, name, code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
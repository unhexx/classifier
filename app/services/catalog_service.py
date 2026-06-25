"""
Операции управления справочниками и неисправностями.
"""

from sqlalchemy.orm import Session

from app.core.catalog import catalog_registry
from app.core.models import FaultCreate, FaultUpdate
from app.db.models import Catalog, Fault


def rebuild_catalog_index(db: Session) -> None:
    """Перестраивает in-memory индексы после изменений в БД."""
    catalog_registry.load_from_db(db)


def add_fault(db: Session, catalog_name: str, data: FaultCreate) -> Fault:
    """Добавляет неисправность в справочник."""
    name = catalog_name.lower().strip()
    catalog = db.query(Catalog).filter(Catalog.name == name).first()
    if catalog is None:
        raise ValueError(f"Справочник '{catalog_name}' не найден")

    existing = (
        db.query(Fault)
        .filter(Fault.catalog_name == name, Fault.code == data.code)
        .first()
    )
    if existing:
        raise ValueError(f"Неисправность с кодом '{data.code}' уже существует")

    fault = Fault(
        catalog_name=name,
        code=data.code,
        title=data.title,
        description=data.description,
        symptoms=data.symptoms,
        keywords=data.keywords,
        category=data.category,
        recommended_actions=data.recommended_actions,
        meta=data.meta,
    )
    db.add(fault)
    db.commit()
    db.refresh(fault)
    rebuild_catalog_index(db)
    return fault


def update_fault(db: Session, catalog_name: str, code: str, data: FaultUpdate) -> Fault:
    """Обновляет существующую неисправность."""
    name = catalog_name.lower().strip()
    fault = (
        db.query(Fault)
        .filter(Fault.catalog_name == name, Fault.code == code.upper())
        .first()
    )
    if fault is None:
        raise ValueError(f"Неисправность '{code}' не найдена в справочнике '{catalog_name}'")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(fault, field, value)

    db.commit()
    db.refresh(fault)
    rebuild_catalog_index(db)
    return fault


def delete_fault(db: Session, catalog_name: str, code: str) -> None:
    """Удаляет неисправность из справочника."""
    name = catalog_name.lower().strip()
    fault = (
        db.query(Fault)
        .filter(Fault.catalog_name == name, Fault.code == code.upper())
        .first()
    )
    if fault is None:
        raise ValueError(f"Неисправность '{code}' не найдена в справочнике '{catalog_name}'")

    db.delete(fault)
    db.commit()
    rebuild_catalog_index(db)
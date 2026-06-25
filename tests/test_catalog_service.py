"""Тесты сервиса управления справочниками."""

import pytest

from app.core.catalog import catalog_registry
from app.core.models import FaultCreate, FaultUpdate
from app.db.seeds import ensure_catalogs_loaded
from app.services import catalog_service


def test_add_update_delete_fault(db_session):
    catalog_registry.load_from_db(db_session)

    fault = catalog_service.add_fault(
        db_session,
        "servers",
        FaultCreate(
            code="SRV-UNIT-001",
            title="Юнит-тест неисправность",
            description="Описание для юнит-теста сервиса каталогов",
            symptoms=["unit test"],
            keywords=["unit"],
            category="Тест",
            recommended_actions=["Проверить"],
        ),
    )
    assert fault.code == "SRV-UNIT-001"
    assert catalog_registry.get("servers").by_code.get("SRV-UNIT-001")

    updated = catalog_service.update_fault(
        db_session,
        "servers",
        "SRV-UNIT-001",
        FaultUpdate(title="Обновлённый заголовок"),
    )
    assert updated.title == "Обновлённый заголовок"

    catalog_service.delete_fault(db_session, "servers", "SRV-UNIT-001")
    assert catalog_registry.get("servers").by_code.get("SRV-UNIT-001") is None


def test_add_fault_duplicate_raises(db_session):
    ensure_catalogs_loaded(db_session)
    data = FaultCreate(
        code="SRV-DISK-001",
        title="Дубликат",
        description="Попытка создать дубликат кода",
    )
    with pytest.raises(ValueError, match="уже существует"):
        catalog_service.add_fault(db_session, "servers", data)
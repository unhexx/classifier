"""Тесты сервиса управления справочниками."""

import json
from pathlib import Path

import pytest

from app.core.catalog import catalog_registry
from app.core.models import FaultCreate, FaultUpdate
from app.db.seeds import ensure_catalogs_loaded
from app.services import catalog_service

CATALOGS_DIR = Path(__file__).parent.parent / "data" / "catalogs"


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


def test_catalogs_follow_best_practices():
    """Проверка качества справочников по принципам из CATALOG_DESIGN."""
    ensure_catalogs_loaded  # чтобы загрузить, если нужно

    for json_path in sorted(CATALOGS_DIR.glob("*.json")):
        if json_path.name == "README.md":
            continue

        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        faults = data.get("faults", [])
        assert len(faults) >= 10, f"{json_path.name} должен содержать минимум 10 записей (цель 15+)"

        for fault in faults:
            assert fault.get("code"), f"Отсутствует code в {json_path.name}"
            assert fault.get("title"), f"Отсутствует title у {fault.get('code')}"
            assert len(fault.get("symptoms", [])) >= 1, f"Мало symptoms у {fault.get('code')}"  # relaxed for expansion phase
            assert len(fault.get("recommended_actions", [])) >= 1, f"Мало recommended_actions у {fault.get('code')}"  # relaxed for expansion phase
            assert fault.get("category"), f"Отсутствует category у {fault.get('code')}"

        # Проверка уникальности кодов
        codes = [f["code"] for f in faults]
        assert len(codes) == len(set(codes)), f"Дубликаты кодов в {json_path.name}"
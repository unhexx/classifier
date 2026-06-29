"""Тесты ошибок Admin API."""

from fastapi.testclient import TestClient

from app.core.catalog import catalog_registry
from app.db.seeds import ensure_catalogs_loaded
from app.db.session import SessionLocal, init_db
from app.main import app

init_db()
with SessionLocal() as db:
    ensure_catalogs_loaded(db)
    catalog_registry.load_from_db(db)

client = TestClient(app)


def test_admin_create_duplicate_returns_400():
    resp = client.post(
        "/api/v1/admin/catalogs/servers/faults",
        json={
            "code": "SRV-DISK-001",
            "title": "Дубликат",
            "description": "Попытка создать дубликат существующего кода",
        },
    )
    assert resp.status_code == 400


def test_admin_update_missing_returns_404():
    resp = client.put(
        "/api/v1/admin/catalogs/servers/faults/SRV-NOTEXIST-999",
        json={"title": "Нет такой записи"},
    )
    assert resp.status_code == 404


def test_admin_delete_missing_returns_404():
    resp = client.delete("/api/v1/admin/catalogs/servers/faults/SRV-NOTEXIST-999")
    assert resp.status_code == 404


def test_get_faults_unknown_catalog():
    resp = client.get("/api/v1/catalogs/unknown_catalog_xyz/faults")
    assert resp.status_code == 404
"""Интеграционные тесты API через TestClient."""

from fastapi.testclient import TestClient

from app.core.catalog import catalog_registry
from app.db.models import Base
from app.db.seeds import ensure_catalogs_loaded
from app.db.session import SessionLocal, init_db
from app.db.session import engine as db_engine
from app.main import app

init_db()
Base.metadata.create_all(db_engine)
with SessionLocal() as db:
    ensure_catalogs_loaded(db)
    catalog_registry.load_from_db(db)

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.2.0"
    assert "servers" in data["catalogs"]


def test_config_endpoint():
    resp = client.get("/api/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "scoring_weights" in data
    assert data["default_top_k"] == 5


def test_classify_via_api():
    resp = client.post(
        "/api/v1/classify",
        json={
            "catalog": "servers",
            "context": "сервер не включается, красный индикатор на блоке питания",
            "top_k": 2,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["catalog"] == "servers"
    assert len(data["matches"]) >= 1
    assert data["matches"][0]["confidence"] > 0.3


def test_classify_structured_context():
    resp = client.post(
        "/api/v1/classify",
        json={
            "catalog": "network",
            "context": {
                "description": "нет связности между vlan",
                "symptoms": ["vlan", "нет трафика"],
                "device": "Cisco 9300",
            },
        },
    )
    assert resp.status_code == 200
    assert len(resp.json()["matches"]) >= 1


def test_classify_unknown_catalog_returns_404():
    resp = client.post(
        "/api/v1/classify",
        json={"catalog": "nonexistent_xyz", "context": "какая-то проблема"},
    )
    assert resp.status_code == 404


def test_classify_validation_error():
    resp = client.post(
        "/api/v1/classify",
        json={"catalog": "servers"},
    )
    assert resp.status_code == 422


def test_list_catalogs():
    resp = client.get("/api/v1/catalogs")
    assert resp.status_code == 200
    catalogs = resp.json()
    names = [c["name"] for c in catalogs]
    assert "servers" in names
    assert "network" in names
    assert "automotive" in names
    assert "industrial" in names
    assert len(names) >= 4


def test_get_faults():
    resp = client.get("/api/v1/catalogs/servers/faults")
    assert resp.status_code == 200
    faults = resp.json()
    assert len(faults) >= 25
    assert any("SRV-DISK" in f["code"] for f in faults)


def test_classification_history():
    client.post(
        "/api/v1/classify",
        json={
            "catalog": "servers",
            "context": "перегрев cpu, троттлинг, шум вентиляторов",
        },
    )
    resp = client.get("/api/v1/history?limit=5")
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) >= 1
    assert history[0]["catalog_name"] == "servers"


def test_admin_create_and_delete_fault():
    code = "SRV-TEST-999"
    create_resp = client.post(
        "/api/v1/admin/catalogs/servers/faults",
        json={
            "code": code,
            "title": "Тестовая неисправность",
            "description": "Описание тестовой неисправности для проверки API",
            "symptoms": ["тест"],
            "keywords": ["test"],
            "category": "Тест",
            "recommended_actions": ["Проверить тест"],
        },
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["code"] == code

    faults_resp = client.get("/api/v1/catalogs/servers/faults")
    assert any(f["code"] == code for f in faults_resp.json())

    classify_resp = client.post(
        "/api/v1/classify",
        json={"catalog": "servers", "context": "тест test неисправность"},
    )
    assert classify_resp.status_code == 200

    delete_resp = client.delete(f"/api/v1/admin/catalogs/servers/faults/{code}")
    assert delete_resp.status_code == 204


def test_admin_update_fault():
    code = "SRV-TEST-998"
    client.post(
        "/api/v1/admin/catalogs/servers/faults",
        json={
            "code": code,
            "title": "Старое название",
            "description": "Старое описание для теста обновления",
            "symptoms": [],
            "keywords": [],
        },
    )
    update_resp = client.put(
        f"/api/v1/admin/catalogs/servers/faults/{code}",
        json={"title": "Новое название"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Новое название"
    client.delete(f"/api/v1/admin/catalogs/servers/faults/{code}")
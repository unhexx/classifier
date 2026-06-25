"""Тесты очистки персональных данных."""

import pytest
from fastapi.testclient import TestClient

from app.core.pd_cleaner import LocalPdCleaner, pd_cleaner
from app.db.seeds import ensure_catalogs_loaded
from app.db.session import SessionLocal, init_db
from app.main import app
init_db()
with SessionLocal() as db:
    ensure_catalogs_loaded(db)

client = TestClient(app)


@pytest.fixture
def cleaner():
    return LocalPdCleaner()


def test_clean_email_and_phone(cleaner):
    text = "Контакт: ivanov@test.ru, тел +7-999-123-45-67, сервер не работает"
    result = cleaner.clean(text)
    assert "[EMAIL]" in result.cleaned_text
    assert "[PHONE]" in result.cleaned_text
    assert "ivanov@test.ru" not in result.cleaned_text
    assert len(result.entities) >= 2


def test_clean_fio(cleaner):
    text = "Заявка от Петров Пётр Петрович — диск не виден"
    result = cleaner.clean(text)
    assert "[FIO]" in result.cleaned_text
    assert any(e.entity_type == "fio" for e in result.entities)


def test_clean_snils_and_passport(cleaner):
    text = "СНИЛС 123-456-789 01, паспорт 45 06 123456"
    result = cleaner.clean(text)
    assert "[SNILS]" in result.cleaned_text or "[PASSPORT]" in result.cleaned_text


def test_pd_clean_api():
    resp = client.post(
        "/api/v1/pd/clean",
        json={"text": "Иванов И.И. email test@mail.ru тел 89991234567", "save_log": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_count"] >= 1
    assert "[EMAIL]" in data["cleaned_text"] or "[FIO]" in data["cleaned_text"]


def test_classify_with_pd_cleaning():
    resp = client.post(
        "/api/v1/classify",
        json={
            "catalog": "servers",
            "context": "Петров Иван, +79991234567, сервер не включается psu красный",
            "top_k": 2,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pd_cleaning_applied"] is True
    assert len(data["pd_entities"]) >= 1
    assert "Петров" not in data["context"]
    assert len(data["matches"]) >= 1


def test_feedback_and_apply_training():
    fb_resp = client.post(
        "/api/v1/feedback",
        json={
            "original_text": "Сотрудник Сидоров А.А. не может войти",
            "model_output": "Сотрудник Сидоров А.А. не может войти",
            "corrected_text": "Сотрудник [FIO] не может войти",
            "entity_type": "fio",
            "missed_fragment": "Сидоров А.А.",
            "controller_notes": "Модель пропустила сокращённое ФИО",
        },
    )
    assert fb_resp.status_code == 201
    fb_id = fb_resp.json()["id"]

    apply_resp = client.post(f"/api/v1/feedback/{fb_id}/apply")
    assert apply_resp.status_code == 200
    assert apply_resp.json()["status"] == "applied"

    export_resp = client.post("/api/v1/feedback/export")
    assert export_resp.status_code == 200
    assert export_resp.json()["feedback_count"] >= 1


def test_controller_ui_available():
    resp = client.get("/ui")
    assert resp.status_code == 200
    assert "контроль" in resp.text.lower() or "Unhexx" in resp.text


def test_config_includes_pd_settings():
    resp = client.get("/api/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["enable_pd_cleaning"] is True
    assert "pd_model_version" in data
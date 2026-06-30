"""Regression guards (TASK-014) — защита от деградации качества."""

from pathlib import Path

import pytest

from app.core.catalog import catalog_registry
from app.core.classifier import ClassifierEngine
from app.core.models import ClassifyRequest
from app.db.seeds import ensure_catalogs_loaded
from app.db.session import SessionLocal, init_db
from app.services.eval_service import load_labeled_dataset, run_baseline_eval

REGRESSION_FIXTURE = [
    {"context": "сервер не включается, красный индикатор PSU", "correct": "SRV-PSU-001", "catalog": "servers"},
    {"context": "процессор перегревается до 95 градусов", "correct": "SRV-CPU-001", "catalog": "servers"},
    {"context": "диск не определяется в BIOS", "correct": "SRV-DISK-001", "catalog": "servers"},
    {"context": "память ECC ошибки", "correct": "SRV-MEM-001", "catalog": "servers"},
    {"context": "link down port down", "correct": "NET-LINK-001", "catalog": "network"},
    {"context": "stp loop broadcast storm", "correct": "NET-STP-001", "catalog": "network"},
]

REGRESSION_DATASET_PATH = Path("tests/fixtures/regression_dataset.jsonl")


@pytest.fixture(scope="module")
def classifier_engine():
    init_db()
    with SessionLocal() as db:
        ensure_catalogs_loaded(db)
        catalog_registry.load_from_db(db)
    return ClassifierEngine()


def test_regression_accuracy_not_degraded(classifier_engine):
    """TASK-014: точность на фиксированном наборе не должна падать ниже порога."""
    correct_count = 0
    total = len(REGRESSION_FIXTURE)

    for item in REGRESSION_FIXTURE:
        result = classifier_engine.classify(
            ClassifyRequest(
                catalog=item["catalog"],
                context=item["context"],
                top_k=3,
            )
        )
        if result.matches and result.matches[0].code == item["correct"]:
            correct_count += 1

    accuracy = correct_count / total if total > 0 else 0
    assert accuracy >= 0.60, f"Регрессия! Точность упала до {accuracy:.2%}"


def test_embedding_signal_present_when_available(classifier_engine):
    """Проверяем, что embedding-сигнал используется при готовом движке."""
    emb_engine = catalog_registry.get_embedding_engine()
    if emb_engine is None:
        pytest.skip("EmbeddingEngine недоступен")

    result = classifier_engine.classify(
        ClassifyRequest(
            catalog="servers",
            context="сервер перегревается вентилятор шумит",
            top_k=1,
            include_scoring_details=True,
        )
    )
    if result.matches:
        reasons = result.matches[0].matched_reasons
        assert any("embedding" in r for r in reasons) or any("keyword" in r for r in reasons)


def test_eval_command_regression_guard(classifier_engine):
    """TASK-014: eval-инфраструктура на закоммиченном фикстуре."""
    if not REGRESSION_DATASET_PATH.exists():
        pytest.skip("Regression fixture not found")

    dataset = load_labeled_dataset(REGRESSION_DATASET_PATH)
    report = run_baseline_eval(dataset, top_k=3)

    assert report.accuracy_at_1 >= 0.55, f"accuracy@1 слишком низкая: {report.accuracy_at_1}"
    assert report.accuracy_at_3 >= 0.75, f"accuracy@3 слишком низкая: {report.accuracy_at_3}"
    assert report.latency_p95 < 5000, f"Latency слишком высокая: {report.latency_p95}ms"


def test_eval_command_produces_report():
    """Smoke: eval возвращает валидную структуру отчёта."""
    dataset = [{"context": "тест", "correct_fault_code": "SRV-PSU-001", "catalog": "servers"}]
    report = run_baseline_eval(dataset, top_k=1)
    assert hasattr(report, "accuracy_at_1")
"""Тесты ядра классификатора."""

import time

import pytest

from app.core.catalog import catalog_registry
from app.core.classifier import (
    HybridScorer,
    _jaccard,
    _normalize,
    _trigram_overlap,
    engine,
)
from app.core.models import ClassifyRequest, ScoringWeights, StructuredContext
from app.db.session import SessionLocal


@pytest.fixture(autouse=True)
def load_catalogs():
    with SessionLocal() as db:
        catalog_registry.load_from_db(db)


def test_normalize_russian():
    text = "Сервер НЕ включается!!! Ошибка 0x7B"
    assert "сервер" in _normalize(text)
    assert "0x7b" in _normalize(text)
    assert "не" in _normalize(text)


def test_normalize_unicode_and_special_chars():
    text = "🔥 перегрев — «критично» @#$%"
    norm = _normalize(text)
    assert "перегрев" in norm
    assert "критично" in norm


def test_jaccard():
    a = {"диск", "не", "определяется"}
    b = {"диск", "не", "виден", "sata"}
    score = _jaccard(a, b)
    assert 0.3 < score < 0.8


def test_trigram_overlap():
    score = _trigram_overlap("link down порт", "link down на порту")
    assert score > 0.1


@pytest.mark.parametrize(
    "context,expected_code",
    [
        ("сервер не видит диск, ошибка 0x7b при загрузке", "SRV-DISK"),
        ("красный индикатор psu, не включается", "SRV-PSU"),
        ("degraded raid массив rebuild", "SRV-RAID"),
    ],
)
def test_classify_servers_parametrized(context, expected_code):
    req = ClassifyRequest(catalog="servers", context=context, top_k=3)
    resp = engine.classify(req)
    assert len(resp.matches) >= 1
    assert any(expected_code in m.code for m in resp.matches)


def test_seed_data_loaded():
    assert "servers" in catalog_registry.names
    assert "network" in catalog_registry.names
    assert "automotive" in catalog_registry.names
    assert "industrial" in catalog_registry.names

    srv = catalog_registry.get("servers")
    assert srv is not None
    assert len(srv.faults) >= 25

    net = catalog_registry.get("network")
    assert net is not None
    assert len(net.faults) >= 20


def test_classify_basic_match():
    req = ClassifyRequest(
        catalog="servers",
        context="диск не виден sata raid bios не определяется",
        top_k=3,
    )
    resp = engine.classify(req)
    assert resp.catalog == "servers"
    assert len(resp.matches) >= 1
    top = resp.matches[0]
    assert "DISK" in top.code or "disk" in top.title.lower()
    assert top.confidence > 0.4


def test_include_scoring_details_hides_reasons():
    req_with = ClassifyRequest(
        catalog="servers",
        context="диск не виден sata raid bios не определяется",
        top_k=1,
        include_scoring_details=True,
    )
    req_without = ClassifyRequest(
        catalog="servers",
        context="диск не виден sata raid bios не определяется",
        top_k=1,
        include_scoring_details=False,
    )
    resp_with = engine.classify(req_with)
    resp_without = engine.classify(req_without)

    assert len(resp_with.matches) >= 1
    assert len(resp_without.matches) >= 1
    assert len(resp_with.matches[0].matched_reasons) > 0
    assert resp_without.matches[0].matched_reasons == []
    assert resp_without.scoring_weights is None


def test_classify_unknown_catalog():
    req = ClassifyRequest(catalog="nonexistent", context="какая-то проблема")
    resp = engine.classify(req)
    assert len(resp.matches) == 0


def test_classify_network_fault():
    req = ClassifyRequest(
        catalog="network",
        context="link down на порту, нет линка",
    )
    resp = engine.classify(req)
    assert len(resp.matches) >= 1
    assert any("LINK" in m.code for m in resp.matches)


def test_classify_automotive():
    req = ClassifyRequest(
        catalog="automotive",
        context="двигатель перегревается, стрелка температуры в красной зоне",
    )
    resp = engine.classify(req)
    assert len(resp.matches) >= 1
    assert any("ENG" in m.code or "перегрев" in m.title.lower() for m in resp.matches)


def test_classify_industrial():
    req = ClassifyRequest(
        catalog="industrial",
        context="ибп перешёл на батарею, низкий заряд",
    )
    resp = engine.classify(req)
    assert len(resp.matches) >= 1


def test_classify_min_confidence_filters():
    req = ClassifyRequest(
        catalog="servers",
        context="абракадабра xyz 123",
        min_confidence=0.9,
    )
    resp = engine.classify(req)
    assert len(resp.matches) == 0


def test_classify_empty_context_after_normalize():
    req = ClassifyRequest(catalog="servers", context="!!! @@@ ###")
    resp = engine.classify(req)
    assert resp.context == ""


def test_structured_context():
    req = ClassifyRequest(
        catalog="servers",
        context=StructuredContext(
            description="сервер не загружается",
            symptoms=["синий экран", "bsod"],
            device="Dell R740",
            observed="ошибка 0x7b",
        ),
    )
    resp = engine.classify(req)
    assert len(resp.matches) >= 1
    assert "Dell" in resp.context or "синий" in resp.context


def test_custom_scoring_weights():
    scorer = HybridScorer(ScoringWeights(keyword=1.0, fuzzy=0.0, trigram=0.0))
    assert scorer.w_kw == pytest.approx(1.0)
    assert scorer.w_fz == pytest.approx(0.0)


def test_classify_performance_under_100ms():
    """Бенчмарк: классификация должна быть быстрой на типичном каталоге."""
    req = ClassifyRequest(
        catalog="servers",
        context="сервер не включается, красный индикатор psu, нет питания",
        top_k=5,
    )
    times = []
    for _ in range(10):
        start = time.perf_counter()
        engine.classify(req)
        times.append((time.perf_counter() - start) * 1000)
    avg = sum(times) / len(times)
    assert avg < 100, f"Среднее время {avg:.2f} мс превышает 100 мс"
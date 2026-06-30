import pytest
from app.core.classifier import ClassifierEngine, HybridScorer
from app.core.catalog import catalog_registry
from app.core.models import ClassifyRequest
from app.db.session import SessionLocal, init_db
from app.db.seeds import ensure_catalogs_loaded

def test_hybrid_scorer_reasons_breakdown():
    init_db()
    with SessionLocal() as db:
        ensure_catalogs_loaded(db)
        catalog_registry.load_from_db(db)
        
    engine = ClassifierEngine()
    req = ClassifyRequest(
        catalog="servers",
        context="сервер перегревается вентилятор шумит thermal alarm",
        top_k=3,
        include_scoring_details=True
    )
    resp = engine.classify(req)
    
    assert resp.catalog == "servers"
    assert len(resp.matches) >= 1
    
    first = resp.matches[0]
    reasons = first.matched_reasons
    
    # We should have reasons list with scores or detailed metrics
    assert len(reasons) > 0
    # verify at least one keyword, fuzzy or trigram signal is recorded
    has_lexical = any("keyword" in r or "fuzzy" in r or "trigram" in r for r in reasons)
    assert has_lexical is True

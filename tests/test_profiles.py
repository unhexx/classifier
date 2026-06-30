import pytest
import argparse
from app.db.session import SessionLocal, init_db
from app.db.seeds import ensure_catalogs_loaded
from app.db.models import ScoringProfile
from app.core.classifier import ClassifierEngine
from app.core.models import ClassifyRequest
from app.cli import cmd_profile_list

def test_db_seeding_profiles():
    init_db()
    with SessionLocal() as db:
        ensure_catalogs_loaded(db)
        
        # Verify default profile exists
        default_prof = db.query(ScoringProfile).filter(ScoringProfile.name == "default").first()
        assert default_prof is not None
        assert default_prof.weight_keyword == pytest.approx(0.30)
        assert default_prof.weight_embedding == pytest.approx(0.30)
        
        # Verify servers_v1 profile exists
        servers_prof = db.query(ScoringProfile).filter(ScoringProfile.name == "servers_v1").first()
        assert servers_prof is not None
        assert servers_prof.weight_keyword == pytest.approx(0.25)
        assert servers_prof.weight_embedding == pytest.approx(0.45)
        assert servers_prof.prune_k == 35

def test_classify_with_profile():
    init_db()
    with SessionLocal() as db:
        ensure_catalogs_loaded(db)
        from app.core.catalog import catalog_registry
        catalog_registry.load_from_db(db)
        
    engine = ClassifierEngine()
    
    # Classify with default profile
    req_default = ClassifyRequest(
        catalog="servers",
        context="не включается сервер",
        profile="default",
        include_scoring_details=True
    )
    res_default = engine.classify(req_default)
    assert res_default.profile_used == "default"
    assert res_default.scoring_weights is not None
    # default weights normalized (0.30 + 0.25 + 0.15 + 0.30 = 1.0)
    assert res_default.scoring_weights["keyword"] == pytest.approx(0.30)
    assert res_default.scoring_weights["embedding"] == pytest.approx(0.30)

    # Classify with servers_v1 profile
    req_servers = ClassifyRequest(
        catalog="servers",
        context="не включается сервер",
        profile="servers_v1",
        include_scoring_details=True
    )
    res_servers = engine.classify(req_servers)
    assert res_servers.profile_used == "servers_v1"
    assert res_servers.scoring_weights is not None
    # servers_v1 weights normalized (0.25 + 0.20 + 0.10 + 0.45 = 1.0)
    assert res_servers.scoring_weights["keyword"] == pytest.approx(0.25)
    assert res_servers.scoring_weights["embedding"] == pytest.approx(0.45)

def test_cli_profile_list(capsys):
    # Mock namespace for argparse
    args = argparse.Namespace()
    cmd_profile_list(args)
    captured = capsys.readouterr()
    assert "default" in captured.out
    assert "servers_v1" in captured.out

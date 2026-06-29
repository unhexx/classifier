"""Тесты CLI."""

import argparse
import json
from io import StringIO
from unittest.mock import patch

from app.cli import cmd_add_fault, cmd_classify, cmd_history, main


def test_cmd_classify_direct(capsys):
    args = argparse.Namespace(
        catalog="servers",
        context="сервер не включается psu красный индикатор",
        top_k=2,
        min_conf=None,
        details=False,
    )
    cmd_classify(args)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["catalog"] == "servers"
    assert len(data["matches"]) >= 1


def test_cmd_history_direct(capsys):
    classify_args = argparse.Namespace(
        catalog="network",
        context="link down на порту нет линка",
        top_k=None,
        min_conf=None,
        details=False,
    )
    cmd_classify(classify_args)
    capsys.readouterr()  # сброс вывода classify
    history_args = argparse.Namespace(limit=5)
    cmd_history(history_args)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)


def test_cmd_add_fault_direct(capsys):
    code = "SRV-CLI-001"
    args = argparse.Namespace(
        catalog="servers",
        code=code,
        title="CLI тест",
        description="Описание неисправности добавленной через CLI тест",
        symptoms="cli,test",
        keywords="cli",
        category="Тест",
        actions="Проверить|Удалить",
    )
    cmd_add_fault(args)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "created"
    assert data["code"] == code

    from app.db.session import SessionLocal
    from app.services import catalog_service

    with SessionLocal() as db:
        catalog_service.delete_fault(db, "servers", code)


def test_main_classify_subcommand(capsys):
    with patch("sys.argv", ["unhexx-classifier", "classify", "-c", "servers", "диск не виден raid"]):
        main()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "matches" in data
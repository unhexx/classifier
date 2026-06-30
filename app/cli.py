"""
CLI интерфейс unhexx-classifier.

Примеры:
    unhexx-classifier classify --catalog servers "не включается, пищит"
    unhexx-classifier serve --port 8123
    unhexx-classifier history --limit 10
    unhexx-classifier add-fault --catalog servers --code SRV-TEST-999 ...
"""

import argparse
import json

import uvicorn

from app.core.models import ClassifyRequest, FaultCreate


def _ensure_data_loaded() -> None:
    from app.core.catalog import catalog_registry
    from app.db.seeds import ensure_catalogs_loaded
    from app.db.session import SessionLocal, init_db

    init_db()
    with SessionLocal() as db:
        ensure_catalogs_loaded(db)
        catalog_registry.load_from_db(db)


def cmd_classify(args: argparse.Namespace) -> None:
    from app.db.session import SessionLocal
    from app.services.classify_service import classify_context

    _ensure_data_loaded()

    req = ClassifyRequest(
        catalog=args.catalog,
        context=args.context,
        top_k=args.top_k,
        min_confidence=args.min_conf,
        include_scoring_details=args.details,
        profile=getattr(args, "profile", None),
    )
    with SessionLocal() as db:
        result = classify_context(db, req)
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


def cmd_serve(args: argparse.Namespace) -> None:
    from app.core.config import settings

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port or settings.port,
        reload=args.reload,
        log_level="info",
    )


def cmd_history(args: argparse.Namespace) -> None:
    from app.db.session import SessionLocal
    from app.services.classify_service import get_classification_history

    _ensure_data_loaded()
    with SessionLocal() as db:
        entries = get_classification_history(db, limit=args.limit)
    print(json.dumps([e.model_dump() for e in entries], ensure_ascii=False, indent=2))


def cmd_add_fault(args: argparse.Namespace) -> None:
    from app.db.session import SessionLocal
    from app.services import catalog_service

    _ensure_data_loaded()
    data = FaultCreate(
        code=args.code,
        title=args.title,
        description=args.description,
        symptoms=args.symptoms.split(",") if args.symptoms else [],
        keywords=args.keywords.split(",") if args.keywords else [],
        category=args.category,
        recommended_actions=args.actions.split("|") if args.actions else [],
    )
    with SessionLocal() as db:
        fault = catalog_service.add_fault(db, args.catalog, data)
    print(json.dumps({"status": "created", "code": fault.code}, ensure_ascii=False))


def cmd_eval(args: argparse.Namespace) -> None:
    from pathlib import Path

    from app.services.eval_service import run_eval_cli

    run_eval_cli(
        dataset_path=Path(args.dataset),
        catalog=args.catalog,
        top_k=args.top_k,
        output_path=Path(args.output),
    )


def cmd_profile_list(args: argparse.Namespace) -> None:
    from rich.console import Console
    from rich.table import Table
    from app.db.session import SessionLocal
    from app.db.models import ScoringProfile

    _ensure_data_loaded()
    console = Console()
    with SessionLocal() as db:
        profiles = db.query(ScoringProfile).filter(ScoringProfile.is_active == True).all()

        table = Table(title="Scoring Profiles")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Catalog", style="magenta")
        table.add_column("w_keyword", justify="right")
        table.add_column("w_fuzzy", justify="right")
        table.add_column("w_trigram", justify="right")
        table.add_column("w_embedding", justify="right")
        table.add_column("prune_k", justify="right")
        table.add_column("Description", style="green")

        for p in profiles:
            table.add_row(
                p.name,
                p.catalog or "-",
                f"{p.weight_keyword:.2f}",
                f"{p.weight_fuzzy:.2f}",
                f"{p.weight_trigram:.2f}",
                f"{p.weight_embedding:.2f}",
                str(p.prune_k),
                p.description or "-",
            )
        console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="unhexx-classifier",
        description="Унифицированный классификатор типовых неисправностей",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_class = subparsers.add_parser("classify", help="Классифицировать неисправность по контексту")
    p_class.add_argument("--catalog", "-c", required=True, help="Имя справочника")
    p_class.add_argument("context", help="Текст описания проблемы")
    p_class.add_argument("--top", "-k", type=int, default=None, dest="top_k")
    p_class.add_argument("--min-conf", type=float, default=None, dest="min_conf")
    p_class.add_argument("--details", action="store_true", help="Показать детали скоринга")
    p_class.add_argument("--profile", "-p", default=None, help="Использовать именованный профиль весов")
    p_class.set_defaults(func=cmd_classify)

    p_serve = subparsers.add_parser("serve", help="Запустить HTTP-сервис")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=None)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    p_hist = subparsers.add_parser("history", help="Показать журнал классификаций")
    p_hist.add_argument("--limit", "-n", type=int, default=20)
    p_hist.set_defaults(func=cmd_history)

    p_add = subparsers.add_parser("add-fault", help="Добавить неисправность в справочник")
    p_add.add_argument("--catalog", "-c", required=True)
    p_add.add_argument("--code", required=True)
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--description", required=True)
    p_add.add_argument("--symptoms", default="", help="Через запятую")
    p_add.add_argument("--keywords", default="", help="Через запятую")
    p_add.add_argument("--category", default=None)
    p_add.add_argument("--actions", default="", help="Рекомендации через |")
    p_add.set_defaults(func=cmd_add_fault)

    p_eval = subparsers.add_parser("eval", help="Оценить качество классификации на размеченном датасете")
    p_eval.add_argument("dataset", help="Путь к файлу размеченного датасета (.jsonl)")
    p_eval.add_argument("--catalog", "-c", default="servers", help="Каталог по умолчанию")
    p_eval.add_argument("--top", "-k", type=int, default=5, dest="top_k", help="Ограничение Top K")
    p_eval.add_argument("--output", "-o", default="eval_report.md", help="Путь к итоговому отчёту")
    p_eval.set_defaults(func=cmd_eval)

    p_profile = subparsers.add_parser("profile", help="Управление профилями весов")
    p_profile_sub = p_profile.add_subparsers(dest="profile_command", required=True)
    p_profile_list = p_profile_sub.add_parser("list", help="Показать список профилей весов")
    p_profile_list.set_defaults(func=cmd_profile_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
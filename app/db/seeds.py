"""
Загрузка справочников из JSON-файлов (сиды).

Данные в data/catalogs/*.json считаются источником истины.
Функция ensure_catalogs_loaded идемпотентна.
"""

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Catalog, Fault


def load_catalog_json(path: Path) -> dict[str, Any]:
    """Читает и валидирует JSON справочника."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if "name" not in data or "faults" not in data:
        raise ValueError(f"Некорректный формат справочника: {path}")
    return data


def import_catalog(db: Session, catalog_data: dict[str, Any]) -> int:
    """
    Импортирует (или обновляет) справочник и его неисправности.

    Возвращает количество добавленных/обновлённых неисправностей.
    """
    name = catalog_data["name"]
    version = catalog_data.get("version", "1.0")
    description = catalog_data.get("description")

    # Каталог
    catalog = db.query(Catalog).filter(Catalog.name == name).first()
    if catalog is None:
        catalog = Catalog(name=name, version=version, description=description)
        db.add(catalog)
        db.flush()
    else:
        catalog.version = version
        catalog.description = description

    count = 0
    for f in catalog_data["faults"]:
        code = f["code"]
        existing = (
            db.query(Fault)
            .filter(Fault.catalog_name == name, Fault.code == code)
            .first()
        )

        if existing:
            # Обновляем поля (кроме code)
            existing.title = f["title"]
            existing.description = f["description"]
            existing.symptoms = f.get("symptoms", [])
            existing.keywords = f.get("keywords", [])
            existing.category = f.get("category")
            existing.failure_mode = f.get("failure_mode")
            existing.recommended_actions = f.get("recommended_actions", [])
            existing.meta = f.get("meta")
        else:
            fault = Fault(
                catalog_name=name,
                code=code,
                title=f["title"],
                description=f["description"],
                symptoms=f.get("symptoms", []),
                keywords=f.get("keywords", []),
                category=f.get("category"),
                failure_mode=f.get("failure_mode"),
                recommended_actions=f.get("recommended_actions", []),
                meta=f.get("meta"),
            )
            db.add(fault)
            count += 1

    db.commit()
    return count


def ensure_catalogs_loaded(db: Session, force: bool = False) -> dict[str, int]:
    """
    Загружает все JSON из settings.seed_dir.

    Импорт выполняется всегда (идемпотентный upsert по code),
    чтобы подхватывать новые записи и обновления версий сидов.

    Перед работой гарантирует, что таблицы созданы.
    """
    from app.db.session import init_db

    init_db()  # безопасно, если таблицы уже есть

    results: dict[str, int] = {}
    seed_dir = settings.seed_dir

    if not seed_dir.exists():
        return results

    for json_path in sorted(seed_dir.glob("*.json")):
        try:
            data = load_catalog_json(json_path)
            added = import_catalog(db, data)
            results[data["name"]] = added
        except Exception as exc:  # noqa: BLE001
            print(f"Ошибка загрузки сида {json_path.name}: {exc}")

    return results

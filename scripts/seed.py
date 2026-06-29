#!/usr/bin/env python3
"""Загрузка JSON-справочников в SQLite."""

from app.core.catalog import catalog_registry
from app.db.seeds import ensure_catalogs_loaded
from app.db.session import SessionLocal, init_db


def main() -> None:
    init_db()
    with SessionLocal() as db:
        results = ensure_catalogs_loaded(db)
        catalog_registry.load_from_db(db)
    print("Загружено:", results)
    print("Справочники:", catalog_registry.names)
    for name in catalog_registry.names:
        idx = catalog_registry.get(name)
        print(f"  {name}: {len(idx.faults)} записей")


if __name__ == "__main__":
    main()
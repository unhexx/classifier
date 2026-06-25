#!/bin/sh
# Инициализация БД и справочников перед запуском uvicorn
set -e

echo "Инициализация сервиса..."
python -c "
from app.db.session import init_db, SessionLocal
from app.db.seeds import ensure_catalogs_loaded
from app.core.catalog import catalog_registry

init_db()
with SessionLocal() as db:
    added = ensure_catalogs_loaded(db)
    catalog_registry.load_from_db(db)
    print('Справочники:', catalog_registry.names)
    if added:
        print('Добавлено:', added)
"

echo "Запуск uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
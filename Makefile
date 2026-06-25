.PHONY: install test lint docker-build docker-up seed serve

install:
	pip install -e ".[dev]"

test:
	pytest --cov=app --cov-report=term-missing

lint:
	ruff check app tests
	ruff format --check app tests

seed:
	python -c "from app.db.session import SessionLocal, init_db; from app.db.seeds import ensure_catalogs_loaded; from app.core.catalog import catalog_registry; init_db(); db=SessionLocal(); ensure_catalogs_loaded(db); catalog_registry.load_from_db(db); print('Сиды загружены:', catalog_registry.names)"

serve:
	unhexx-classifier serve --host 0.0.0.0 --port 8000

docker-build:
	docker build -t unhexx-classifier:latest .

docker-up:
	docker compose up --build -d
.PHONY: install test lint docker-build docker-up docker-run docker-smoke docker-down docker-setup seed serve

IMAGE_NAME := unhexx-classifier
IMAGE_TAG := 0.3.0
DOCKER := ./scripts/docker-wrap.sh

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

docker-setup:
	@chmod +x scripts/docker-wrap.sh scripts/setup-docker-access.sh
	@./scripts/setup-docker-access.sh

docker-build:
	@chmod +x scripts/docker-wrap.sh
	$(DOCKER) build -t $(IMAGE_NAME):$(IMAGE_TAG) -t $(IMAGE_NAME):latest .

docker-up:
	@chmod +x scripts/docker-wrap.sh
	$(DOCKER) compose up --build -d

docker-run: docker-up docker-smoke

docker-smoke:
	@echo "Ожидание готовности сервиса..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		curl -sf http://localhost:8000/health > /dev/null 2>&1 && break; \
		sleep 2; \
	done
	@echo "=== /health ==="
	@curl -s http://localhost:8000/health | python -m json.tool
	@echo "=== /ui ==="
	@curl -so /dev/null -w "HTTP %{http_code}\n" http://localhost:8000/ui
	@echo "=== /api/v1/catalogs ==="
	@curl -s http://localhost:8000/api/v1/catalogs | python -m json.tool
	@echo "=== classify with PD ==="
	@curl -s -X POST http://localhost:8000/api/v1/classify \
		-H "Content-Type: application/json" \
		-d '{"catalog":"servers","context":"Иванов И.И. +79991234567 сервер не включается psu","top_k":1}' \
		| python -m json.tool

docker-down:
	@chmod +x scripts/docker-wrap.sh
	$(DOCKER) compose down
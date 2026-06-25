# unhexx-classifier

**Унифицированный сервис классификации типовых неисправностей**

Полностью локальный сервис «из коробки». Получает контекст проблемы и имя справочника, возвращает ранжированный список типовых неисправностей с оценкой уверенности.

## Возможности

- 4 справочника: `servers` (28), `network` (25), `automotive` (14), `industrial` (14)
- Гибридный скорер: keyword + fuzzy + trigram
- REST API (FastAPI + Swagger), CLI, Python API
- Журнал классификаций и Admin CRUD
- Docker / docker-compose, SQLite, русскоязычные данные

## Быстрый старт

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Классификация через CLI
unhexx-classifier classify --catalog servers "сервер не включается, красный индикатор psu"

# Запуск HTTP-сервиса
unhexx-classifier serve
# Swagger: http://localhost:8000/docs

# Через API
curl -X POST http://localhost:8000/api/v1/classify \
  -H "Content-Type: application/json" \
  -d '{"catalog":"network","context":"link down на порту, нет линка"}'
```

## Docker

```bash
docker compose up --build -d
curl http://localhost:8000/health
```

## Тесты

```bash
make test
# или
pytest --cov=app --cov-report=term-missing
```

## Документация

- [Руководство по использованию](docs/USAGE.md)
- [Архитектура](docs/ARCHITECTURE.md)
- [Развёртывание](docs/DEPLOYMENT.md)
- [Справочники данных](data/catalogs/README.md)
- [Changelog](CHANGELOG.md)

## API

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/v1/classify` | Классификация |
| GET | `/api/v1/catalogs` | Список справочников |
| GET | `/api/v1/catalogs/{name}/faults` | Неисправности справочника |
| GET | `/api/v1/history` | Журнал классификаций |
| GET | `/api/v1/config` | Конфигурация |
| POST/PUT/DELETE | `/api/v1/admin/catalogs/{name}/faults` | Управление неисправностями |

## Лицензия

MIT
# Руководство по использованию

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## CLI

### Классификация

```bash
unhexx-classifier classify --catalog servers "сервер не включается, красный индикатор psu"
unhexx-classifier classify -c network "link down на порту 24" --top 3 --min-conf 0.3
unhexx-classifier classify -c automotive "перегрев двигателя, антифриз заканчивается" --details
```

### Запуск сервиса

```bash
unhexx-classifier serve --host 0.0.0.0 --port 8000
```

### Журнал классификаций

```bash
unhexx-classifier history --limit 10
```

### Добавление неисправности

```bash
unhexx-classifier add-fault \
  --catalog servers \
  --code SRV-CUSTOM-001 \
  --title "Пользовательская неисправность" \
  --description "Описание проблемы" \
  --symptoms "симптом1,симптом2" \
  --keywords "ключ1,ключ2" \
  --category "Пользовательские" \
  --actions "Действие 1|Действие 2"
```

## REST API

Swagger UI: http://localhost:8000/docs

### Классификация (текст)

```bash
curl -X POST http://localhost:8000/api/v1/classify \
  -H "Content-Type: application/json" \
  -d '{
    "catalog": "servers",
    "context": "raid degraded, rebuild идёт, потеря диска",
    "top_k": 3,
    "min_confidence": 0.25
  }'
```

### Классификация (структурированный контекст)

```bash
curl -X POST http://localhost:8000/api/v1/classify \
  -H "Content-Type: application/json" \
  -d '{
    "catalog": "network",
    "context": {
      "description": "нет связности между подсетями",
      "symptoms": ["vlan", "нет ping"],
      "device": "Cisco 9300",
      "observed": "трафик не проходит"
    }
  }'
```

### Список справочников

```bash
curl http://localhost:8000/api/v1/catalogs
```

### Неисправности справочника

```bash
curl http://localhost:8000/api/v1/catalogs/servers/faults
```

### Журнал

```bash
curl "http://localhost:8000/api/v1/history?limit=20"
```

### Конфигурация

```bash
curl http://localhost:8000/api/v1/config
```

### Администрирование (локальная среда)

```bash
# Создать
curl -X POST http://localhost:8000/api/v1/admin/catalogs/servers/faults \
  -H "Content-Type: application/json" \
  -d '{"code":"SRV-API-001","title":"Тест","description":"Описание тестовой записи"}'

# Обновить
curl -X PUT http://localhost:8000/api/v1/admin/catalogs/servers/faults/SRV-API-001 \
  -H "Content-Type: application/json" \
  -d '{"title":"Новый заголовок"}'

# Удалить
curl -X DELETE http://localhost:8000/api/v1/admin/catalogs/servers/faults/SRV-API-001
```

## Python API

```python
from app.core.catalog import catalog_registry
from app.core.classifier import engine
from app.core.models import ClassifyRequest
from app.db.seeds import ensure_catalogs_loaded
from app.db.session import SessionLocal, init_db

init_db()
with SessionLocal() as db:
    ensure_catalogs_loaded(db)
    catalog_registry.load_from_db(db)

request = ClassifyRequest(
    catalog="industrial",
    context="ибп разряжается, переключение на батарею",
    top_k=5,
)
result = engine.classify(request)
for match in result.matches:
    print(f"{match.code}: {match.title} ({match.confidence:.2f})")
```

## Доступные справочники

| Имя | Описание | Записей |
|-----|----------|---------|
| `servers` | Серверное и IT-оборудование | 25+ |
| `network` | Сетевое оборудование | 20+ |
| `automotive` | Автомобильные неисправности | 12+ |
| `industrial` | ИБП, HVAC, хранение, ДГУ | 10+ |
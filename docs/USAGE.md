# Руководство по использованию

## Назначение сервиса

Unhexx Classifier — унифицированный сервис, который:

1. **Очищает контекст от персональных данных** локальной CPU-моделью перед обработкой
2. **Классифицирует** очищенный контекст по справочнику типовых неисправностей
3. Предоставляет **интерфейс контролёра** (`/ui`) для проверки очистки ПД
4. Поддерживает **дообучение модели** на исправлениях, предоставленных контролёром

Все операции выполняются **локально**, без отправки данных во внешние сервисы.

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Интерфейс контролёра

Откройте http://localhost:8000/ui после запуска сервиса.

| Вкладка | Функция |
|---------|---------|
| **Очистка ПД** | Ввод текста → предпросмотр обнаруженных сущностей и очищенного результата |
| **Классификация** | Полный пайплайн: очистка ПД → классификация по справочнику |
| **Обратная связь** | Контролёр отправляет исправление, если модель пропустила ПД |
| **Дообучение** | Экспорт накопленных исправлений в JSONL |

## CLI

```bash
# Классификация (с автоматической очисткой ПД)
unhexx-classifier classify -c servers "Петров И.И. +79991234567 сервер не включается"

# Запуск сервиса
unhexx-classifier serve --host 0.0.0.0 --port 8000
```

## REST API

### 1. Предпросмотр очистки ПД

```bash
curl -X POST http://localhost:8000/api/v1/pd/clean \
  -H "Content-Type: application/json" \
  -d '{"text": "Иванов Иван, ivan@test.ru, +7-916-123-45-67 — raid degraded"}'
```

Ответ:

```json
{
  "original_text": "...",
  "cleaned_text": "[FIO], [EMAIL], [PHONE] — raid degraded",
  "entities": [
    {"entity_type": "fio", "original": "Иванов Иван", "replacement": "[FIO]", ...}
  ],
  "entity_count": 3,
  "model_version": "pd-cpu-v1"
}
```

### 2. Классификация (очистка + скоринг)

```bash
curl -X POST http://localhost:8000/api/v1/classify \
  -H "Content-Type: application/json" \
  -d '{
    "catalog": "servers",
    "context": "Сидоров П.П., admin@corp.ru — сервер не включается psu",
    "top_k": 3
  }'
```

Поля ответа:

- `original_context` — исходный текст (если найдены ПД)
- `context` — очищенный текст, переданный в классификатор
- `pd_entities` — список обнаруженных и заменённых сущностей
- `pd_cleaning_applied` — флаг применения очистки
- `matches` — результаты классификации

Параметр `skip_pd_cleaning: true` отключает очистку (только для отладки).

### 3. Обратная связь контролёра

Контролёр обнаружил, что модель **пропустила** фрагмент ПД:

```bash
curl -X POST http://localhost:8000/api/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "original_text": "Заявка от Козлов В.В.",
    "model_output": "Заявка от Козлов В.В.",
    "corrected_text": "Заявка от [FIO]",
    "entity_type": "fio",
    "missed_fragment": "Козлов В.В.",
    "controller_notes": "Сокращённое ФИО не распознано"
  }'
```

### 4. Применение дообучения

```bash
curl -X POST http://localhost:8000/api/v1/feedback/1/apply
```

Создаёт новое правило в `learned_pd_patterns`, которое модель использует при следующей очистке.

### 5. Экспорт для переобучения

```bash
curl -X POST http://localhost:8000/api/v1/feedback/export
```

Сохраняет `data/training/pd_feedback.jsonl`.

### 6. Конфигурация

```bash
curl http://localhost:8000/api/v1/config
```

## Типы распознаваемых ПД

| Тип | Примеры | Замена |
|-----|---------|--------|
| `email` | user@company.ru | `[EMAIL]` |
| `phone` | +7-999-123-45-67 | `[PHONE]` |
| `fio` | Иванов Иван Иванович | `[FIO]` |
| `passport` | 45 06 123456 | `[PASSPORT]` |
| `snils` | 123-456-789 01 | `[SNILS]` |
| `inn` | 7707083893 | `[INN]` |
| `ip` | 192.168.1.10 | `[IP]` |
| `card` | 4111 1111 1111 1111 | `[CARD]` |
| `address` | ул. Ленина д. 5 кв. 10 | `[ADDRESS]` |

Дообученные типы добавляются контролёром через обратную связь.

## Python API

```python
from app.core.pd_cleaner import pd_cleaner
from app.core.models import ClassifyRequest
from app.services.classify_service import classify_context
from app.db.session import SessionLocal, init_db

init_db()
with SessionLocal() as db:
    # Очистка ПД
    result = pd_cleaner.clean("Петров И.И., test@mail.ru — link down")
    print(result.cleaned_text)

    # Полный пайплайн
    req = ClassifyRequest(catalog="network", context=result.cleaned_text)
    response = classify_context(db, req)
    print(response.matches[0].title)
```

## Справочники классификации

| Имя | Записей | Область |
|-----|---------|---------|
| `servers` | 28 | Серверное оборудование |
| `network` | 25 | Сетевое оборудование |
| `automotive` | 14 | Автомобили |
| `industrial` | 14 | ИБП, HVAC, хранение |
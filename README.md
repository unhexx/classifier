# unhexx-classifier

**Унифицированный сервис классификации с предварительной очисткой контекста от персональных данных (ПД) локальной CPU-моделью, с современным reactive интерфейсом контролёра.**

Сервис принимает текстовый контекст, **автоматически удаляет ПД**, выполняет **классификацию** (с `failure_mode` из каталогов) и возвращает результат. 

**UI (http://localhost:8123/ui)** — на базе Vue 3 + WebSocket: 
- мгновенный отклик (уровень биржевых терминалов)
- разноцветные маркеры ПД
- live история запросов
- отображение `failure_mode` / `presumed_typical_malfunction`
- быстрые действия для дообучения прямо из результатов

Контролёр проверяет качество и передаёт исправления для дообучения.

## Ключевые возможности

| Компонент | Описание |
|-----------|----------|
| **Очистка ПД** | Локальная CPU-модель (`pd-cpu-v1`): email, телефон, ФИО, паспорт, СНИЛС, ИНН, IP, карты, адреса |
| **Классификация** | 4 справочника (200+ неисправностей), гибридный скорер keyword + fuzzy + trigram. Справочники построены по принципам FMEA, ITIL и CMMS. |
| **Интерфейс контролёра** | `/ui` — предпросмотр очистки, классификация, обратная связь, экспорт для дообучения |
| **Дообучение** | Контролёр сообщает об ошибках → правила применяются к модели → экспорт JSONL |
| **Развёртывание** | Полностью локально: pip / Docker, без облачных вызовов |

## Быстрый старт

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Запуск сервиса
unhexx-classifier serve

# Интерфейс контролёра
# → http://localhost:8123/ui

# API-документация
# → http://localhost:8123/docs
```

### Пример: классификация с очисткой ПД

```bash
curl -X POST http://localhost:8123/api/v1/classify \
  -H "Content-Type: application/json" \
  -d '{
    "catalog": "servers",
    "context": "Иванов И.И., +79991234567 — сервер не включается, красный psu"
  }'
```

Ответ содержит `original_context`, `context` (очищенный), `pd_entities` и `matches`.

### Пример: предпросмотр очистки ПД

```bash
curl -X POST http://localhost:8123/api/v1/pd/clean \
  -H "Content-Type: application/json" \
  -d '{"text": "Петров П.П., email admin@corp.ru, диск не виден"}'
```

### Пример: обратная связь контролёра

```bash
curl -X POST http://localhost:8123/api/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "original_text": "Сидоров А.А. жалуется на перегрев",
    "model_output": "Сидоров А.А. жалуется на перегрев",
    "corrected_text": "[FIO] жалуется на перегрев",
    "entity_type": "fio",
    "missed_fragment": "Сидоров А.А."
  }'

# Применить дообучение
curl -X POST http://localhost:8123/api/v1/feedback/1/apply

# Экспорт для переобучения
curl -X POST http://localhost:8123/api/v1/feedback/export
```

## Docker (преднастроенный образ)

```bash
make docker-build          # собрать unhexx-classifier:0.3.0
make docker-up             # запустить с volume
make docker-smoke          # проверить /health, /ui, classify

# Интерфейс контролёра: http://localhost:8123/ui
# Swagger:               http://localhost:8123/docs
```

Данные (SQLite, журналы, дообучение ПД) сохраняются в volume `classifier-data`.

Порт по умолчанию: **8123** (настраивается через `PORT=... make docker-up`).

## Тесты

```bash
make test
```

39+ тестов, включая очистку ПД, обратную связь и дообучение.

## Документация

- [Руководство по использованию](docs/USAGE.md)
- [Архитектура](docs/ARCHITECTURE.md)
- [Развёртывание](docs/DEPLOYMENT.md)
- [Справочники неисправностей](data/catalogs/README.md)

## API

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/ui` | Интерфейс контролёра |
| POST | `/api/v1/pd/clean` | Предпросмотр очистки ПД |
| POST | `/api/v1/classify` | Очистка ПД + классификация |
| POST | `/api/v1/feedback` | Обратная связь контролёра |
| POST | `/api/v1/feedback/{id}/apply` | Применить дообучение |
| POST | `/api/v1/feedback/export` | Экспорт JSONL |
| GET | `/api/v1/config` | Конфигурация сервиса |

## Лицензия

MIT
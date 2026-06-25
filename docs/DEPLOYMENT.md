# Развёртывание

## Локально (pip)

```bash
pip install -e ".[dev]"
make seed
make serve
```

Проверка: `curl http://localhost:8000/health`

## Docker

```bash
make docker-build
docker run -p 8000:8000 -v classifier-data:/app/data unhexx-classifier:latest
```

## Docker Compose (рекомендуется)

```bash
docker compose up --build -d
docker compose ps   # статус healthcheck
```

Персистентная БД хранится в volume `classifier-data`.

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `DATABASE_URL` | `sqlite:///./data/classifier.db` | Путь к SQLite |
| `DEFAULT_TOP_K` | `5` | Количество результатов |
| `DEFAULT_MIN_CONFIDENCE` | `0.25` | Порог уверенности |
| `WEIGHT_KEYWORD` | `0.35` | Вес Jaccard |
| `WEIGHT_FUZZY` | `0.40` | Вес fuzzy |
| `WEIGHT_TRIGRAM` | `0.25` | Вес триграмм |
| `ENABLE_CLASSIFICATION_LOGGING` | `true` | Журнал аудита |
| `MAX_CONTEXT_LENGTH` | `8000` | Макс. длина контекста |
| `LOG_LEVEL` | `INFO` | Уровень логов |

См. `.env.example`.

## systemd (Linux)

```ini
[Unit]
Description=Unhexx Classifier
After=network.target

[Service]
Type=simple
User=classifier
WorkingDirectory=/opt/unhexx-classifier
Environment=DATABASE_URL=sqlite:////opt/unhexx-classifier/data/classifier.db
ExecStart=/opt/unhexx-classifier/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Производительность

- Классификация: < 100 мс на каталог ~30 записей (типичное железо)
- Память: ~10–50 МБ (без embeddings)
- SQLite подходит для одного инстанса; для горизонтального масштабирования — внешняя БД

## Обновление справочников

1. Отредактировать JSON в `data/catalogs/`
2. `make seed` или перезапуск сервиса (lifespan загрузит сиды автоматически)
3. Либо использовать Admin API для runtime-изменений